"""Crosswalk from the layer0 exercise catalog's `movement_patterns` vocabulary
to the rx_engine's single `PROGRESSION_RULES` key (#335 Phase 2b, identity slice).

`layer0.exercises.movement_patterns` is a multi-valued biomechanical taxonomy
(20 values: Squat, Hinge, Push-H/Push-V, Pull-H/Pull-V, Single-Leg, Anti-*,
Carry, Rotation, Hip-Ext, Abduction, Isometric, Locomotion,
Balance / Proprioception, Stretch). The rx progression engine
(`calculations.PROGRESSION_RULES`) keys off a SINGLE pattern that selects which
dimension to bump (Squat/Hinge/Lunge/Push/Pull/Core/Carry/Rotation/Plyo/
Balance/Grip/Mobility/Locomotion/Conditioning/Various).

Once the strength-rx path keys off the layer0 EX-id (the single source of truth
the synthesizer already emits) instead of the v1 `exercise_inventory.exercise`
name, the engine reads `movement_patterns` from layer0 and collapses it here to
the progression key — replacing the old `exercise_inventory.movement_pattern`
single-value column. Deterministic; no LLM, no new vocabulary.

Design: `aidstation-sources/designs/Layer4_StrengthRxSingleSourceOfTruth_335_Phase2b_Design_v1.md` (D3).
"""

from __future__ import annotations


# Curated v1-name → layer0 EX-id map (#335 Phase 2b D2; fuzzy + Andy's HITL
# review, 2026-06-16). The single source of truth for resolving a logged/seeded
# exercise NAME to its canonical layer0 EX-id. Two consumers read it:
#   - init_db `_PG_MIGRATIONS` — the idempotent `current_rx` backfill.
#   - rx_engine.apply_session_outcome — the write-path EX-id resolution (#430
#     Slice C), so newly-logged exercises self-heal their `layer0_exercise_id`
#     and key the progression off layer0 movement_patterns.
# Names absent here resolve to None → the caller falls back to the legacy
# exercise_inventory pattern (status quo; no regression). "Back Squat" and the
# FIT-generic "Squat" both map to EX001 by design.
NAME_TO_EX_ID: dict[str, str] = {
    "Back Squat": "EX001",
    "Squat": "EX001",
    "Barbell Hip Thrust": "EX019",
    "Bulgarian Split Squat": "EX021",
    "Goblet Squat": "EX002",
    "Dead Bug": "EX217",
    "Farmer Carry": "EX009",
    "Single-Arm DB Row (Staggered)": "EX078",
    "Lateral Raise": "EX233",
    "Plank": "EX216",
    "Side Plank": "EX219",
    "Pull Up": "EX006",
    "Push Up": "EX228",
    "Bench Press": "EX229",
    "Deadlift": "EX230",
    "Triceps Extension": "EX235",
    # The 4 that needed new layer0 entries (0011_add_strength_rx_exercises.sql,
    # EX246-EX249; Trigger #2, Andy-ratified 2026-06-16).
    "Row": "EX246",
    "Curl": "EX247",
    "Sit Up": "EX248",
    "KB Halo": "EX249",
}


# layer0 movement_pattern value → rx PROGRESSION_RULES key. Values not listed
# here fall through to "Various" (the PROGRESSION_RULES fallback row).
_LAYER0_TO_PROGRESSION: dict[str, str] = {
    "Squat": "Squat",
    "Hinge": "Hinge",
    "Hip-Ext": "Hinge",            # hip extension is the hinge load pattern
    "Single-Leg": "Lunge",         # layer0 has no "Lunge"; unilateral → Lunge rules
    "Push-H": "Push",
    "Push-V": "Push",
    "Pull-H": "Pull",
    "Pull-V": "Pull",
    "Carry": "Carry",
    "Rotation": "Rotation",
    "Anti-Rotation": "Core",
    "Anti-Extension": "Core",
    "Anti-Flexion": "Core",
    "Anti-Lateral-Flexion": "Core",
    "Anti-Adduction": "Core",
    "Isometric": "Core",           # loaded/bodyweight trunk holds
    "Locomotion": "Locomotion",
    "Balance / Proprioception": "Balance",
    "Stretch": "Mobility",
    # "Abduction" (hip-abduction accessory) has no clean progression analogue →
    # left out so it falls through to "Various".
}

# When an exercise carries several patterns, pick the one that best determines
# how it loads. Heavy bilateral/loadable compounds first (weight progression),
# then unilateral, then the lower-CNS accessory families. First match wins; an
# exercise whose patterns are all unmapped resolves to "Various".
_PROGRESSION_PRIORITY: tuple[str, ...] = (
    "Squat", "Hinge", "Lunge", "Push", "Pull", "Carry",
    "Rotation", "Core", "Balance", "Locomotion", "Mobility",
)

_FALLBACK = "Various"


def progression_pattern(movement_patterns: list[str] | None) -> str:
    """Collapse a layer0 `movement_patterns` list to a single rx PROGRESSION_RULES
    key. Empty/None or all-unmapped → "Various" (the engine's fallback row).

    Multi-pattern exercises resolve to the highest-priority mapped pattern
    (`_PROGRESSION_PRIORITY`), so a Single-Leg + Anti-Rotation step-up loads as
    a "Lunge" (weight progression) rather than as "Core".
    """
    if not movement_patterns:
        return _FALLBACK
    mapped = {
        _LAYER0_TO_PROGRESSION[p]
        for p in movement_patterns
        if p in _LAYER0_TO_PROGRESSION
    }
    if not mapped:
        return _FALLBACK
    for key in _PROGRESSION_PRIORITY:
        if key in mapped:
            return key
    # Mapped to a key outside the priority list (none today) — return any.
    return next(iter(mapped))
