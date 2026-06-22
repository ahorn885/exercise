"""Public `equipment_items.tag` → layer0 `equipment_required` canonical token.

The purchases page's "unlocks N exercises" count + the per-recommendation
impacted-exercise list were derived from `exercise_equipment` (the public
exercise↔equipment int-id join on the retired v1 catalog). The catalog
unification re-sources them from the single canonical catalog: count the active
`layer0.exercises` whose `equipment_required` contains the layer0 token a
purchase recommendation's equipment maps to.

The two equipment vocabularies are semantically aligned but not string-equal
(casing / plural / qualifier drift: `dumbbells`→`Dumbbell`, `sled`→`Weighted
sled`, `barbell`→`Barbell (Olympic)` label). This crosswalk bridges them on the
stable snake_case `tag`. Tags with no layer0 strength-equipment home — cardio
machines (`treadmill`-as-cardio aside), discipline craft (`kayak`, `road_bike`),
and gym machines layer0 models generically (`smith_machine`, `lat_pulldown`,
`pec_deck`) — are deliberately absent: those exercises carry a coarser layer0
token (e.g. `Cable machine`) or none, so a specific mapping would over- or
mis-count. An absent tag resolves to a 0 count (no layer0 exercise unlocked),
matching the pre-unification reality for cardio/craft equipment.

Every value here is one of the active `layer0.exercises.equipment_required`
tokens (verified against prod 2026-06-21), so each mapped tag yields ≥1 exercise.
"""

from __future__ import annotations

# tag → layer0 equipment_required token (exact, case-sensitive).
EQUIPMENT_TAG_TO_LAYER0_TOKEN: dict[str, str] = {
    'ab_wheel': 'Ab wheel',
    'bench_adjustable': 'Bench',
    'bench_flat': 'Bench',
    'bosu': 'BOSU ball',
    'barbell': 'Barbell',
    'battle_ropes': 'Battle ropes',
    'cable_machine': 'Cable machine',
    'cycling_trainer': 'Cycling trainer',
    'dip_bars': 'Dip bars',
    'dumbbells': 'Dumbbell',
    'foam_roller': 'Foam roller',
    'rings': 'Gymnastic rings',
    'hack_squat': 'Hack squat machine',
    'hangboard': 'Hangboard',
    'kettlebell': 'Kettlebell',
    'leg_curl': 'Leg curl machine',
    'leg_extension': 'Leg extension machine',
    'leg_press': 'Leg press machine',
    'med_ball': 'Medicine ball',
    'slam_ball': 'Medicine ball',   # slam-ball work resolves to the med-ball token
    'plyo_box': 'Plyo box',
    'pull_up_bar': 'Pull-up bar',
    'resistance_bands': 'Resistance band',
    'rice_bucket': 'Rice bucket',
    'rowing_erg': 'Rowing ergometer',
    'sandbag': 'Sandbag',
    'sled': 'Weighted sled',
    'squat_rack': 'Squat rack',
    'stability_ball': 'Stability ball',
    'trx': 'TRX / suspension trainer',
    'treadmill': 'Treadmill',
}


def layer0_token_for_tag(tag):
    """The layer0 equipment token a purchase-recommendation tag unlocks, or None
    when the equipment has no layer0 strength-exercise home."""
    return EQUIPMENT_TAG_TO_LAYER0_TOKEN.get(tag)


def layer0_equipment_exercise_counts(db) -> dict[str, int]:
    """`{equipment_token: active-exercise count}` over all `layer0.exercises`
    equipment_required tokens — one pass, for the purchases list."""
    rows = db.execute(
        "SELECT equip, COUNT(*) AS cnt FROM ("
        "  SELECT exercise_id, unnest(equipment_required) AS equip"
        "    FROM layer0.exercises WHERE superseded_at IS NULL"
        ") t GROUP BY equip"
    ).fetchall()
    return {r['equip']: r['cnt'] for r in rows}
