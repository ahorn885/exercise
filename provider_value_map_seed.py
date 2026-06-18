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


def provider_value_map_rows():
    """Yield `provider_value_map` seed rows as tuples matching the table columns:
    (provider, data_type, direction, source_value, canonical_kind,
     canonical_value, match_kind, confidence, no_canonical_match, notes).

    Strength names + the Garmin coarse-cardio map (Slice 1). Fine-D-id cardio
    rows from the matrix are authored in Slice 2.
    """
    for name, ex_id in STRENGTH_NAME_TO_EX_ID.items():
        yield ('garmin', 'strength', 'in', name, 'ex_id', ex_id, 'manual', 1.0, False, None)
    for type_key, sport in GARMIN_TYPE_TO_PLAN_SPORT.items():
        yield ('garmin', 'cardio', 'in', type_key, 'modality', sport, 'manual', 1.0, False, None)
