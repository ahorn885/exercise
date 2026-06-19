"""Consolidated provider → canonical seed for `provider_value_map` (#681 §4 wave).

The single git authoring surface + canonical-store seed for the provider data
translation layer. Replaces the formerly-scattered Python dicts (previously in
`layer0_progression.NAME_TO_EX_ID`, `provider_strength_resolve` aliases, and
`garmin_connect.GARMIN_TYPE_TO_PLAN_SPORT`) with one module that both the
in-process consumers import AND `init_db` materializes into the
`provider_value_map` table (the runtime-canonical store the API / later slices
read). Per `designs/ProviderTranslation_StorageSchema_681_BuildDesign_v1.md`
(Slice 1) + parent `specs/Provider_Data_Translation_Layer_Spec_v1.md` §4.2.

Per-entry provenance for the strength maps lives in the #679 docs:
`designs/ProviderTranslation_GarminStrength_679_Design_v1.md` +
`..._679_CandidateBatch_v1.md` (Batch A/B/C, Andy-ratified 2026-06-17).
"""

from __future__ import annotations


# Coarse / manual-log canonical name → layer0 EX-id (formerly
# `layer0_progression.NAME_TO_EX_ID`, #335 Phase 2b). Also the
# category-collapse backstop target set (a FIT category name resolves here).
STRENGTH_COARSE_NAME_TO_EX_ID: dict[str, str] = {
    'Back Squat': 'EX001',
    'Squat': 'EX001',
    'Barbell Hip Thrust': 'EX019',
    'Bulgarian Split Squat': 'EX021',
    'Goblet Squat': 'EX002',
    'Dead Bug': 'EX217',
    'Farmer Carry': 'EX009',
    'Single-Arm DB Row (Staggered)': 'EX078',
    'Lateral Raise': 'EX233',
    'Plank': 'EX216',
    'Side Plank': 'EX219',
    'Pull Up': 'EX006',
    'Push Up': 'EX228',
    'Bench Press': 'EX229',
    'Deadlift': 'EX230',
    'Triceps Extension': 'EX235',
    'Row': 'EX246',
    'Curl': 'EX247',
    'Sit Up': 'EX248',
    'KB Halo': 'EX249',
}


# Garmin FIT subtype name → specific layer0 EX-id (#679; token-set-exact
# Garmin specifics + Andy-ratified Batch A). Preserves specificity over the
# coarse backstop ("Dumbbell Hammer Curl" → EX234, not coarse "Curl").
GARMIN_STRENGTH_ALIASES: dict[str, str] = {
    'Barbell Back Squat': 'EX001',
    'Bear Crawl': 'EX240',
    'Bicycle Crunch': 'EX224',
    'Burpee': 'EX238',
    'Dumbbell Bulgarian Split Squat': 'EX021',
    'Dumbbell Hammer Curl': 'EX234',
    'Dumbbell Reverse Wrist Curl': 'EX111',
    'Mountain Climber': 'EX221',
    'Rope Climb': 'EX195',
    'Seated Calf Raise': 'EX026',
    'Single Arm Dumbbell Bench Press': 'EX242',
    'Wide Grip Lat Pulldown': 'EX080',
    'Goblet Squat': 'EX002',
    'Barbell Front Squat': 'EX231',
    'Thoracic Rotation': 'EX016',
    'Cable External Rotation': 'EX082',
    'Band External Rotation': 'EX082',
    'Face Pull': 'EX081',
    'Fire Hydrant Kicks': 'EX042',
    'Seated Barbell Good Morning': 'EX061',
    'Split Barbell Good Morning': 'EX061',
    'Single Leg Barbell Good Morning': 'EX061',
    'High Box Jump': 'EX007',
    'Barbell Reverse Wrist Curl': 'EX111',
    'Reverse Grip Wrist Curl': 'EX111',
    'Weighted Bicycle Crunch': 'EX224',
    'Weighted Mountain Climber': 'EX221',
    'Barbell Bulgarian Split Squat': 'EX021',
    'Wall Slide': 'EX065',
    'Overhead Bulgarian Split Squat': 'EX251',
    'Barbell Hack Squat': 'EX252',
    'Barbell Box Squat': 'EX253',
    'Wide Grip Seated Cable Row': 'EX265',
    'Close Grip Lat Pulldown': 'EX266',
    'Kettlebell Flye': 'EX271',
    'Standing Calf Raise': 'EX258',
    'Spiderman Plank': 'EX280',
    'Side Kick Plank': 'EX281',
    'Side Plank Lift': 'EX282',
}


# Andy's logged-prescription vocabulary (his real `current_rx` names) →
# layer0 EX-id (#679, mapped against a read-only prod query 2026-06-17).
LOGGED_NAME_ALIASES: dict[str, str] = {
    '4-Side Box Step-Up/Off': 'EX024',
    '7/3 Repeaters (Hangboard)': 'EX100',
    'Ab Wheel Rollout': 'EX222',
    'Asymmetric Stab. Ball Push-Up': 'EX272',
    'Back Extension / Rev. Hyper': 'EX220',
    'Band Pull-Apart': 'EX066',
    'Bent-Over Barbell Row': 'EX246',
    'Bird Dog': 'EX218',
    'Box Jump': 'EX007',
    'Cable Woodchop (High-to-Low)': 'EX087',
    'Cable Woodchop (Low-to-High)': 'EX284',
    'Clamshell (Banded)': 'EX040',
    'Copenhagen Plank': 'EX012',
    'Deadlift (Standard)': 'EX230',
    'Dumbbell Chest Press': 'EX229',
    'Elevated Reverse Lunge': 'EX022',
    'Fire Hydrant (Banded)': 'EX042',
    'Front Squat': 'EX231',
    'Glute Bridge / Hip Thrust': 'EX039',
    'Glute Kickback (Banded)': 'EX042',
    'Good Morning': 'EX061',
    'Half-Kneeling 1-Arm Cable Row': 'EX078',
    'Hangboard Max Hangs': 'EX100',
    'Hanging Knee Raise': 'EX223',
    'Hillbounding': 'EX036',
    'Isometric Lunge Hold': 'EX038',
    'KB Swing on Inverted BOSU': 'EX031',
    'Kettlebell Swing (Two-Hand)': 'EX031',
    'Lat Pulldown': 'EX080',
    'Med Ball Torso Rotation (Seated)': 'EX088',
    'Med Ball Wall Throws (Rotational)': 'EX085',
    'Mountain Climbers': 'EX221',
    'Nordic Hamstring Curl': 'EX020',
    'Oblique Press (Contralateral)': 'EX011',
    'Overhead Carry': 'EX244',
    'Pallof Press': 'EX011',
    'Pistol Squat': 'EX028',
    'Plank with Rotation': 'EX285',
    'Pull-Up': 'EX006',
    'Push-Up': 'EX228',
    'Rapid Calf Raises': 'EX025',
    'Rice Bucket': 'EX104',
    'Romanian Deadlift': 'EX003',
    'Russian Twist (Feet Elevated)': 'EX088',
    'Sandbag / Pack Carry (Bear Hug)': 'EX279',
    'Seated Cable Row': 'EX079',
    'Side Plank + Banded Leg Raise': 'EX286',
    'Side Split Lunges (Deep)': 'EX023',
    'Single-Leg Calf Raise': 'EX025',
    'Single-Leg Deadlift': 'EX004',
    'Sled Pull (Hand-Over-Hand)': 'EX030',
    'Sled Push': 'EX029',
    'Stability Ball Seated Shoulder Press': 'EX098',
    'Stability Ball Single-Arm DB Press': 'EX242',
    'Standing Figure-4 Stretch': 'EX015',
    'Standing Hip Flexor Stretch': 'EX046',
    'Step-Down (Eccentric)': 'EX117',
    'Suitcase Carry': 'EX243',
    'TRX Mtn Climber / Unstable Bar': 'EX221',
    'Towel Pull-Up': 'EX267',
    'Turkish Get-Up': 'EX239',
    'Wall Calf Stretch': 'EX047',
    'Wall Chest / Doorway Stretch': 'EX077',
    'Wall Sit': 'EX037',
    'Weighted Box Step-Up': 'EX119',
    'Banded Pull-Through': 'EX256',
    'Battle Ropes': 'EX287',
    'Dip': 'EX268',
    'Forearm Wrist Curls': 'EX289',
    'Front Lever Progression': 'EX264',
    'KB Clean & Press': 'EX270',
    'KB Snatch': 'EX273',
    'KB Sumo Deadlift': 'EX254',
    'KB Windmill': 'EX275',
    'L-Sit Pull-Up': 'EX263',
    'Lunge to Rotation (Slam Ball/DB)': 'EX260',
    'Pedal Stance Deadlift': 'EX259',
    'Push Press': 'EX269',
    'Rack Carry': 'EX278',
    'Renegade Row (Plank + DB Row)': 'EX261',
    'Sandbag Get-Up': 'EX277',
    'Seated Glute Squeeze (Isometric)': 'EX283',
    'Single-Arm KB Swing': 'EX274',
    'Single-Leg Glute Bridge': 'EX255',
    'Stability Ball Hamstring Curl': 'EX257',
    'Straight-Arm Lat Pulldown': 'EX262',
    'Sumo Deadlift High Pull': 'EX276',
    'Treadwall Intervals': 'EX288',
    'Walking Lunge': 'EX250',
}


# Merged strength resolution map (alias step + backfill read it). Later maps
# win on a key collision; the one overlap ("Goblet Squat") agrees on EX002.
STRENGTH_NAME_TO_EX_ID: dict[str, str] = {
    **STRENGTH_COARSE_NAME_TO_EX_ID,
    **GARMIN_STRENGTH_ALIASES,
    **LOGGED_NAME_ALIASES,
}


# Garmin activity typeKey → coarse `_plan_sport_type` (formerly
# `garmin_connect.GARMIN_TYPE_TO_PLAN_SPORT`; the wired Garmin cardio path).
GARMIN_TYPE_TO_PLAN_SPORT: dict[str, str] = {
    'running': 'running',
    'trail_running': 'running',
    'treadmill_running': 'running',
    'track_running': 'running',
    'cycling': 'cycling',
    'road_biking': 'cycling',
    'mountain_biking': 'cycling',
    'gravel_cycling': 'cycling',
    'indoor_cycling': 'cycling',
    'virtual_ride': 'cycling',
    'strength_training': 'strength_training',
    'swimming': 'swimming',
    'open_water_swimming': 'swimming',
    'hiking': 'hiking',
    'walking': 'walking',
}


# Provider cardio activity-type → canonical discipline (#681 §4 Slice 2; the
# fine-D-id fidelity upgrade, matrix-v2 §1 option C). Each value is a
# `(canonical_kind, canonical_value)` pair:
#   ('discipline', 'D-0xx') — bucket-1 fine layer0 discipline; the coarse
#                             `_plan_sport_type` is DERIVED via
#                             `provider_cardio_resolve.DISCIPLINE_TO_PLAN_SPORT`
#                             (the collapse is a canon-internal fact, kept next to
#                             the resolver — NOT a value-map row; ratified Q3).
#   ('modality', '<coarse>') — bucket-1 coarse-only (walking / strength_training):
#                              a real activity with no race-discipline D-id (§12).
#   ('bucket3', None)        — an explicitly-recorded "known, deliberately
#                              unmapped" type (record raw + surface; §6/§12 — e.g.
#                              Rowing, mint reversed 2026-06-18). Any source value
#                              NOT listed here also resolves to bucket-3 at runtime
#                              (record-don't-drop); only the §12-dispositioned
#                              training modalities are pinned explicitly.
# Transcribed verbatim from `specs/Provider_Inbound_Matrix_v2.md` (Andy-ratified):
# Strava §2.2, RWGPS §10.1, Wahoo §10.2 (source_value = workout_type_id), TP §11.1.
# Garmin's own typeKey→D-id rows land with the live-path repoint (Slice 2b).
CARDIO_DISCIPLINE_MAP: dict[str, dict[str, tuple[str, str | None]]] = {
    # ── Strava `sport_type` (§2.2) ──────────────────────────────────────────
    'strava': {
        'Run': ('discipline', 'D-002'),
        'TrailRun': ('discipline', 'D-001'),
        'VirtualRun': ('discipline', 'D-002'),        # closest; raw kept
        'Ride': ('discipline', 'D-006'),
        'VirtualRide': ('discipline', 'D-006'),        # indoor; + indoor flag (2b)
        'MountainBikeRide': ('discipline', 'D-008'),
        'EMountainBikeRide': ('discipline', 'D-008'),  # e-assist flag in raw
        'GravelRide': ('discipline', 'D-030'),
        'EBikeRide': ('discipline', 'D-006'),          # e-assist flag in raw
        'Handcycle': ('discipline', 'D-006'),          # adaptive flag in raw
        'Velomobile': ('discipline', 'D-006'),
        'Swim': ('discipline', 'D-004'),
        'Hike': ('discipline', 'D-003'),
        'Snowshoe': ('discipline', 'D-017'),
        'Kayaking': ('discipline', 'D-010'),
        'Canoeing': ('discipline', 'D-011'),
        'StandUpPaddling': ('discipline', 'D-032'),
        'RockClimbing': ('discipline', 'D-012'),
        'AlpineSki': ('discipline', 'D-022'),
        'NordicSki': ('discipline', 'D-028'),
        'BackcountrySki': ('discipline', 'D-021'),     # the skimo signal
        'RollerSki': ('discipline', 'D-028'),          # dryland proxy; raw flags rollerski
        'WeightTraining': ('modality', 'strength_training'),
        'Walk': ('modality', 'walking'),
        'Rowing': ('bucket3', None),                   # §6/§12 — training modality
        'VirtualRow': ('bucket3', None),
    },
    # ── Ride with GPS `activity_type` (§10.1; namespaced family:variant) ─────
    'rwgps': {
        'cycling:road': ('discipline', 'D-006'),
        'cycling:gravel': ('discipline', 'D-030'),
        'cycling:mountain': ('discipline', 'D-008'),
        'cycling:generic': ('discipline', 'D-006'),
        'cycling:commute': ('discipline', 'D-006'),
        'cycling:indoor': ('discipline', 'D-006'),     # + indoor flag (2b)
        'cycling:virtual': ('discipline', 'D-006'),
        'cycling:cyclocross': ('discipline', 'D-006'),
        'cycling:recumbent': ('discipline', 'D-006'),
        'cycling:hand_cycling': ('discipline', 'D-006'),
        'e_biking:road': ('discipline', 'D-006'),      # e-bike flag in raw
        'e_biking:mountain': ('discipline', 'D-008'),
        'e_biking:generic': ('discipline', 'D-006'),
        'running:road': ('discipline', 'D-002'),
        'running:trail': ('discipline', 'D-001'),
        'running:generic': ('discipline', 'D-002'),
        'running:indoor': ('discipline', 'D-002'),
        'walking:hiking': ('discipline', 'D-003'),
        'walking:generic': ('modality', 'walking'),
        'walking:indoor': ('modality', 'walking'),
        'walking:speed': ('modality', 'walking'),
        'swimming:generic': ('discipline', 'D-004'),
        'swimming:lap': ('discipline', 'D-004'),
        'swimming:open_water': ('discipline', 'D-004'),
        'snow:alpine_skiing': ('discipline', 'D-022'),
        'snow:cross_country_skiing': ('discipline', 'D-028'),
        'snow:snowshoeing': ('discipline', 'D-017'),
    },
    # ── Wahoo `workout_type_id` (§10.2; source_value = the integer id) ───────
    'wahoo': {
        '0': ('discipline', 'D-006'),    # BIKING
        '15': ('discipline', 'D-006'),   # BIKING_ROAD
        '16': ('discipline', 'D-006'),   # BIKING_TRACK
        '14': ('discipline', 'D-006'),   # BIKING_RECUMBENT
        '12': ('discipline', 'D-006'),   # BIKING_INDOOR  (+ indoor flag 2b)
        '49': ('discipline', 'D-006'),   # BIKING_INDOOR_CLASS
        '68': ('discipline', 'D-006'),   # BIKING_VIRTUAL
        '61': ('discipline', 'D-006'),   # BIKING_INDOOR_TRAINER (KICKR)
        '70': ('discipline', 'D-006'),   # HANDCYCLING
        '64': ('discipline', 'D-006'),   # EBIKING
        '13': ('discipline', 'D-008'),   # BIKING_MOUNTAIN
        '11': ('discipline', 'D-006'),   # BIKING_CYCLECROSS (closest)
        '1': ('discipline', 'D-002'),    # RUNNING
        '3': ('discipline', 'D-002'),    # RUNNING_TRACK
        '5': ('discipline', 'D-002'),    # RUNNING_TREADMILL
        '67': ('discipline', 'D-002'),   # RUNNING_RACE
        '71': ('discipline', 'D-002'),   # RUNNING_INDOOR_VIRTUAL
        '19': ('discipline', 'D-002'),   # FE_TREADMILL
        '4': ('discipline', 'D-001'),    # RUNNING_TRAIL
        '9': ('discipline', 'D-003'),    # HIKING
        '10': ('discipline', 'D-018'),   # MOUNTAINEERING
        '25': ('discipline', 'D-004'),   # SWIMMING_LAP
        '26': ('discipline', 'D-004'),   # SWIMMING_OPEN_WATER
        '29': ('discipline', 'D-022'),   # SKIING_DOWNHILL
        '28': ('discipline', 'D-022'),   # SKIING
        '30': ('discipline', 'D-028'),   # SKIING_CROSS_COUNTRY
        '37': ('discipline', 'D-011'),   # CANOEING
        '38': ('discipline', 'D-010'),   # KAYAKING
        '41': ('discipline', 'D-032'),   # STAND_UP_PADDLE_BOARD
        '6': ('modality', 'walking'),    # WALKING
        '7': ('modality', 'walking'),    # WALKING_*
        '8': ('modality', 'walking'),    # WALKING_*
        '56': ('modality', 'walking'),   # WALKING_TREADMILL
        '39': ('bucket3', None),         # ROWING — §6/§12
        '22': ('bucket3', None),         # FE_ROWER — §6/§12
    },
    # ── TrainingPeaks `WorkoutType` (§11.1) ─────────────────────────────────
    'trainingpeaks': {
        'swim': ('discipline', 'D-004'),
        'bike': ('discipline', 'D-006'),
        'mtb': ('discipline', 'D-008'),
        'Mountain Bike': ('discipline', 'D-008'),
        'run': ('discipline', 'D-002'),       # no road/trail split → D-001 not derivable
        'xc-ski': ('discipline', 'D-028'),
        'walk': ('modality', 'walking'),
        'strength': ('modality', 'strength_training'),
        'rowing': ('bucket3', None),          # §6/§12 — mint reversed
    },
}


def provider_value_map_rows():
    """Yield `provider_value_map` seed rows as tuples matching the table columns:
    (provider, data_type, direction, source_value, canonical_kind,
     canonical_value, match_kind, confidence, no_canonical_match, notes).

    Strength names + the Garmin coarse-cardio map (Slice 1) + the fine-D-id
    provider cardio crosswalk (Slice 2; CARDIO_DISCIPLINE_MAP).
    """
    for name, ex_id in STRENGTH_NAME_TO_EX_ID.items():
        yield ('garmin', 'strength', 'in', name, 'ex_id', ex_id, 'manual', 1.0, False, None)
    for type_key, sport in GARMIN_TYPE_TO_PLAN_SPORT.items():
        yield ('garmin', 'cardio', 'in', type_key, 'modality', sport, 'manual', 1.0, False, None)
    for provider, mapping in CARDIO_DISCIPLINE_MAP.items():
        for source_value, (kind, value) in mapping.items():
            if kind == 'bucket3':
                # explicit known-unmapped: record raw, no canonical match
                yield (provider, 'cardio', 'in', source_value, 'discipline', None,
                       'manual', 1.0, True, None)
            else:
                yield (provider, 'cardio', 'in', source_value, kind, value,
                       'manual', 1.0, False, None)
