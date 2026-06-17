"""Resolve a logged strength exercise NAME to its canonical layer0 EX-id (#679).

First concrete **inbound** slice of the provider data translation layer
(`aidstation-sources/specs/Provider_Data_Translation_Layer_Spec` §6.1; design
`aidstation-sources/designs/ProviderTranslation_GarminStrength_679_Design_v1.md`).

After #430 Slice C the rx write path keys off the layer0 EX-id, but a Garmin FIT
upload's *specific* exercise name (e.g. "Barbell Back Squat" — 1 of 92 squat
subtypes the parser can emit) rarely matched the 20-entry curated
`NAME_TO_EX_ID`, so most Garmin-logged lifts landed as NULL-EX-id rows and never
surfaced as capacity-derived loads in plan-gen — defeating the #335 goal for the
athlete who dogfoods via Garmin.

This module resolves a name through three additive steps (design §3.1), called
from the single write chokepoint `rx_engine.apply_session_outcome`:

    1. ALIAS    — exact-authored name → EX-id. Merges the curated `NAME_TO_EX_ID`
                  (also read by the init_db `current_rx` backfill) with the
                  token-set-exact Garmin specifics authored for #679. Preserves
                  specificity: "Dumbbell Hammer Curl" → EX234 (neutral-grip
                  hammer curl), NOT the coarse "Curl" → EX247.
    2. CATEGORY — backstop only. Collapse a specific Garmin subtype to its coarse
                  FIT category name, then through the SAME ratified coarse
                  `NAME_TO_EX_ID` ("Barbell Bench Press" → "Bench Press" → EX229).
                  No new vocabulary: only categories already mapped to a coarse
                  EX-id resolve here; the rest fall through to bucket-3.
    3. BUCKET-3 — no match → `(None, 'bucket3')`. The caller records the lift
                  (record-don't-drop) with no canonical EX-id instead of silently
                  treating it as a brand-new exercise on every ingest (design §4).
                  A later wave surfaces it inline in completed history.

Fuzzy (non-token-exact) candidate matches and Garmin categories with no coarse
layer0 home are deliberately NOT auto-added here — they are HITL decisions Andy
ratifies in one consolidated batch (design §5, D-10), then authored into
`GARMIN_STRENGTH_ALIASES` / extended onto the coarse map.
"""

from __future__ import annotations

from layer0_progression import NAME_TO_EX_ID


# Garmin FIT subtype name → specific layer0 EX-id. Authored for #679 as the
# token-set-exact matches between the Garmin name space (garmin_fit_parser's
# `_EXERCISE_SUBTYPE_MAP`, 1,239 subtypes) and the strength-relevant layer0
# qualified names — identical normalized token sets (equipment synonyms folded:
# bb↔barbell, db↔dumbbell, …). These are deterministic equivalences, not fuzzy
# judgement calls, so they seed without per-row HITL. Each adds SPECIFICITY the
# coarse category backstop can't: "Dumbbell Hammer Curl" → EX234 (hammer),
# distinct from the coarse "Curl" → EX247; "Seated Calf Raise" → EX026 (the Calf
# Raise category has no coarse home, so without this it would bucket-3).
# Entries already present verbatim in NAME_TO_EX_ID (Dead Bug, Side Plank,
# Sit Up) are intentionally omitted — the merge in `_alias_map()` covers them.
GARMIN_STRENGTH_ALIASES: dict[str, str] = {
    "Barbell Back Squat": "EX001",            # Back Squat (Barbell)
    "Bear Crawl": "EX240",                    # Bear Crawl
    "Bicycle Crunch": "EX224",                # Bicycle Crunch
    "Burpee": "EX238",                        # Burpee
    "Dumbbell Bulgarian Split Squat": "EX021",  # Bulgarian Split Squat (DB)
    "Dumbbell Hammer Curl": "EX234",          # Hammer Curl (DB)
    "Dumbbell Reverse Wrist Curl": "EX111",   # Reverse Wrist Curl (DB)
    "Mountain Climber": "EX221",              # Mountain Climber
    "Rope Climb": "EX195",                    # Rope Climb
    "Seated Calf Raise": "EX026",             # Seated Calf Raise
    "Single Arm Dumbbell Bench Press": "EX242",  # Single-Arm DB Bench Press
    "Wide Grip Lat Pulldown": "EX080",        # Lat Pulldown (Wide Grip)
    # Batch A — Andy-ratified Garmin specifics → existing EX-ids (2026-06-17,
    # designs/ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md). These
    # map to a live exercise that covers the same stimulus; the equipment-prefix
    # the Garmin name carries is dropped because the EX-id is the same lift.
    "Goblet Squat": "EX002",                  # Goblet Squat (DB/KB)
    "Barbell Front Squat": "EX231",           # Front Squat (Barbell/KB)
    "Thoracic Rotation": "EX016",             # Thoracic Rotation Drill
    "Cable External Rotation": "EX082",       # External Rotation (Band/Cable)
    "Band External Rotation": "EX082",        # External Rotation (Band/Cable)
    "Face Pull": "EX081",                     # Band Face Pull
    "Fire Hydrant Kicks": "EX042",            # Donkey Kick / Fire Hydrant
    "Seated Barbell Good Morning": "EX061",   # Good Morning (Barbell)
    "Split Barbell Good Morning": "EX061",    # Good Morning (Barbell)
    "Single Leg Barbell Good Morning": "EX061",  # Good Morning (Barbell)
    "High Box Jump": "EX007",                 # Box Jump
    "Barbell Reverse Wrist Curl": "EX111",    # Reverse Wrist Curl (DB)
    "Reverse Grip Wrist Curl": "EX111",       # Reverse Wrist Curl (DB)
    "Weighted Bicycle Crunch": "EX224",       # Bicycle Crunch
    "Weighted Mountain Climber": "EX221",     # Mountain Climber
    "Barbell Bulgarian Split Squat": "EX021",  # Bulgarian Split Squat (DB)
    "Wall Slide": "EX065",                    # Scapular Wall Slide
    # Batch-A names Andy ratified as NEW exercises (minted in 0012-0015) →
    # their new EX-ids (2026-06-17).
    "Overhead Bulgarian Split Squat": "EX251",
    "Barbell Hack Squat": "EX252",
    "Barbell Box Squat": "EX253",
    "Wide Grip Seated Cable Row": "EX265",
    "Close Grip Lat Pulldown": "EX266",
    "Kettlebell Flye": "EX271",               # → Chest Flye
    "Standing Calf Raise": "EX258",
    "Spiderman Plank": "EX280",
    "Side Kick Plank": "EX281",
    "Side Plank Lift": "EX282",
}


# Andy's logged-prescription vocabulary → existing layer0 EX-id. These are the
# names that show up in his `current_rx` (the v2 synthesizer's output + manual
# setup), NOT Garmin FIT subtype names — mapped 2026-06-17 against his real
# logged set (read-only prod query) on his "map them all" greenlight. Each maps
# to a live exercise covering the same movement; `H` matches are the same lift
# bar naming/equipment, `M` are a close variant routed to the nearest canonical
# (audit list: designs/ProviderTranslation_GarminStrength_679_CandidateBatch_v1.md
# §"current_rx vocabulary"). Names with no existing home are NOT here — they're
# the new-exercise batch (Trigger #2, authored separately).
LOGGED_NAME_ALIASES: dict[str, str] = {
    "4-Side Box Step-Up/Off": "EX024",
    "7/3 Repeaters (Hangboard)": "EX100",
    "Ab Wheel Rollout": "EX222",
    "Asymmetric Stab. Ball Push-Up": "EX272",
    "Back Extension / Rev. Hyper": "EX220",
    "Band Pull-Apart": "EX066",
    "Bent-Over Barbell Row": "EX246",
    "Bird Dog": "EX218",
    "Box Jump": "EX007",
    "Cable Woodchop (High-to-Low)": "EX087",
    "Cable Woodchop (Low-to-High)": "EX284",
    "Clamshell (Banded)": "EX040",
    "Copenhagen Plank": "EX012",
    "Deadlift (Standard)": "EX230",
    "Dumbbell Chest Press": "EX229",
    "Elevated Reverse Lunge": "EX022",
    "Fire Hydrant (Banded)": "EX042",
    "Front Squat": "EX231",
    "Glute Bridge / Hip Thrust": "EX039",
    "Glute Kickback (Banded)": "EX042",
    "Good Morning": "EX061",
    "Half-Kneeling 1-Arm Cable Row": "EX078",
    "Hangboard Max Hangs": "EX100",
    "Hanging Knee Raise": "EX223",
    "Hillbounding": "EX036",
    "Isometric Lunge Hold": "EX038",
    "KB Swing on Inverted BOSU": "EX031",
    "Kettlebell Swing (Two-Hand)": "EX031",
    "Lat Pulldown": "EX080",
    "Med Ball Torso Rotation (Seated)": "EX088",
    "Med Ball Wall Throws (Rotational)": "EX085",
    "Mountain Climbers": "EX221",
    "Nordic Hamstring Curl": "EX020",
    "Oblique Press (Contralateral)": "EX011",
    "Overhead Carry": "EX244",
    "Pallof Press": "EX011",
    "Pistol Squat": "EX028",
    "Plank with Rotation": "EX285",
    "Pull-Up": "EX006",
    "Push-Up": "EX228",
    "Rapid Calf Raises": "EX025",
    "Rice Bucket": "EX104",
    "Romanian Deadlift": "EX003",
    "Russian Twist (Feet Elevated)": "EX088",
    "Sandbag / Pack Carry (Bear Hug)": "EX279",
    "Seated Cable Row": "EX079",
    "Side Plank + Banded Leg Raise": "EX286",
    "Side Split Lunges (Deep)": "EX023",
    "Single-Leg Calf Raise": "EX025",
    "Single-Leg Deadlift": "EX004",
    "Sled Pull (Hand-Over-Hand)": "EX030",
    "Sled Push": "EX029",
    "Stability Ball Seated Shoulder Press": "EX098",
    "Stability Ball Single-Arm DB Press": "EX242",
    "Standing Figure-4 Stretch": "EX015",
    "Standing Hip Flexor Stretch": "EX046",
    "Step-Down (Eccentric)": "EX117",
    "Suitcase Carry": "EX243",
    "TRX Mtn Climber / Unstable Bar": "EX221",
    "Towel Pull-Up": "EX267",
    "Turkish Get-Up": "EX239",
    "Wall Calf Stretch": "EX047",
    "Wall Chest / Doorway Stretch": "EX077",
    "Wall Sit": "EX037",
    "Weighted Box Step-Up": "EX119",
    # current_rx names Andy ratified as NEW exercises (minted in 0012-0015) →
    # their new EX-ids (2026-06-17). These previously fell to bucket-3.
    "Banded Pull-Through": "EX256",
    "Battle Ropes": "EX287",
    "Dip": "EX268",
    "Forearm Wrist Curls": "EX289",
    "Front Lever Progression": "EX264",
    "KB Clean & Press": "EX270",
    "KB Snatch": "EX273",
    "KB Sumo Deadlift": "EX254",
    "KB Windmill": "EX275",
    "L-Sit Pull-Up": "EX263",
    "Lunge to Rotation (Slam Ball/DB)": "EX260",
    "Pedal Stance Deadlift": "EX259",
    "Push Press": "EX269",
    "Rack Carry": "EX278",
    "Renegade Row (Plank + DB Row)": "EX261",
    "Sandbag Get-Up": "EX277",
    "Seated Glute Squeeze (Isometric)": "EX283",
    "Single-Arm KB Swing": "EX274",
    "Single-Leg Glute Bridge": "EX255",
    "Stability Ball Hamstring Curl": "EX257",
    "Straight-Arm Lat Pulldown": "EX262",
    "Sumo Deadlift High Pull": "EX276",
    "Treadwall Intervals": "EX288",
    "Walking Lunge": "EX250",
}


# Inverted Garmin subtype-name → coarse FIT category name, derived from
# garmin_fit_parser's maps (the SAME source the parser emits names from, so the
# reverse map cannot drift from the names actually seen). Built lazily and
# cached: importing the parser pulls `fit_tool`, and this module must stay
# importable on the manual-log path even where the category backstop is never
# exercised. Degrades to {} if the parser/fit_tool is unavailable → the category
# step no-ops and the name falls through to bucket-3 (safe).
_SUBTYPE_TO_CATEGORY: dict[str, str] | None = None


def _subtype_to_category() -> dict[str, str]:
    global _SUBTYPE_TO_CATEGORY
    if _SUBTYPE_TO_CATEGORY is not None:
        return _SUBTYPE_TO_CATEGORY
    try:
        from garmin_fit_parser import (
            _EXERCISE_SUBTYPE_MAP,
            _EXERCISE_CATEGORY_MAP,
        )
    except Exception:
        _SUBTYPE_TO_CATEGORY = {}
        return _SUBTYPE_TO_CATEGORY
    inv: dict[str, str] = {}
    for cat_int, subs in _EXERCISE_SUBTYPE_MAP.items():
        cat_name = _EXERCISE_CATEGORY_MAP.get(cat_int)
        if not cat_name:
            continue
        for human in subs.values():
            inv.setdefault(human, cat_name)  # first category wins on dup names
    _SUBTYPE_TO_CATEGORY = inv
    return _SUBTYPE_TO_CATEGORY


def _alias_map() -> dict[str, str]:
    """Curated `NAME_TO_EX_ID` (coarse + manual-log names) extended by the #679
    Garmin specifics and Andy's logged-prescription vocabulary. Later maps win on
    a key collision (none today — the three keyspaces are disjoint)."""
    return {**NAME_TO_EX_ID, **GARMIN_STRENGTH_ALIASES, **LOGGED_NAME_ALIASES}


def resolve_strength_ex_id(exercise, *, subtype_to_category=None):
    """Resolve a logged strength exercise NAME to `(layer0_ex_id, match_kind)`.

    `match_kind`:
      - ``'alias'``    — exact-authored name → specific EX-id.
      - ``'category'`` — coarse category-collapse backstop → coarse EX-id.
      - ``'bucket3'``  — no match; `layer0_ex_id` is None (record-don't-drop).

    `subtype_to_category` is injectable for tests; production passes None and the
    lazily-built reverse map (from `garmin_fit_parser`) is used.
    """
    if not exercise:
        return None, 'bucket3'
    ex_id = _alias_map().get(exercise)
    if ex_id:
        return ex_id, 'alias'
    s2c = _subtype_to_category() if subtype_to_category is None else subtype_to_category
    cat_name = s2c.get(exercise)
    if cat_name:
        ex_id = NAME_TO_EX_ID.get(cat_name)
        if ex_id:
            return ex_id, 'category'
    return None, 'bucket3'
