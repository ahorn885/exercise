"""Tests for the Vocab Audit §5 cleanup rules."""
from __future__ import annotations

from etl.layer0.vocabulary_transforms import (
    transform_body_part_string,
    transform_equipment_string,
    validate_against_canonical,
)


# ---------------------------------------------------------------------------
# Body-part transform tests (Vocab Audit §5 col-13 renames)
# ---------------------------------------------------------------------------

def test_body_part_lumbar_to_lower_back():
    assert transform_body_part_string("Lumbar") == ["Lower back"]


def test_body_part_cervical_spine_to_neck():
    assert transform_body_part_string("Cervical Spine") == ["Neck"]


def test_body_part_thoracic_to_upper_back():
    assert transform_body_part_string("Thoracic") == ["Upper back"]


def test_body_part_acl_rename():
    assert transform_body_part_string("Anterior Cruciate Ligament") == ["ACL"]


def test_body_part_hip_abductor_merges_to_glute():
    assert transform_body_part_string("Hip Abductor") == ["Glute"]


def test_body_part_chest_rib_splits():
    out = transform_body_part_string("Chest/Rib")
    assert out == ["Chest", "Rib"]


def test_body_part_shoulder_wrist_splits():
    out = transform_body_part_string("Shoulder/Wrist")
    assert out == ["Shoulder", "Wrist"]


def test_body_part_compound_with_canonical():
    # The col-13 string "Knee, Lumbar, Shoulder/Wrist" should yield three
    # canonical body parts (Lumbar→Lower back, Shoulder/Wrist split).
    out = transform_body_part_string("Knee, Lumbar, Shoulder/Wrist")
    assert out == ["Knee", "Lower back", "Shoulder", "Wrist"]


def test_body_part_systemic_flags_pass_through():
    # Cardiac, Cognitive, Lungs, GI, Skin etc. are health conditions, not
    # body parts. They pass through unchanged — the alignment validator
    # surfaces them as warnings (correct behavior).
    out = transform_body_part_string("Cardiac, Cognitive")
    assert out == ["Cardiac", "Cognitive"]


# ---------------------------------------------------------------------------
# Equipment transform tests (existing)
# ---------------------------------------------------------------------------




def test_passthrough_canonical_items():
    assert transform_equipment_string("Barbell, Rack") == ["Barbell", "Rack"]


def test_rename_band_family():
    assert transform_equipment_string("Band") == ["Resistance Band"]
    assert transform_equipment_string("Rubber Band") == ["Resistance Band"]


def test_rename_mtb():
    assert transform_equipment_string("MTB") == ["Mountain Bike"]


def test_rename_cable_to_cable_machine():
    assert transform_equipment_string("Cable") == ["Cable Machine"]


def test_rename_box_to_plyo_box():
    assert transform_equipment_string("Box") == ["Plyo Box"]
    assert transform_equipment_string("Vault Box") == ["Plyo Box"]


def test_rename_vest_family():
    assert transform_equipment_string("Vest") == ["Weighted Vest"]
    assert transform_equipment_string("Weight Vest") == ["Weighted Vest"]


def test_rename_shoes_to_running_shoes():
    assert transform_equipment_string("Shoes") == ["Running Shoes"]


def test_rename_rings_to_gymnastic_rings():
    assert transform_equipment_string("Rings") == ["Gymnastic Rings"]


def test_rename_trainer_to_bike_trainer():
    assert transform_equipment_string("Trainer") == ["Bike Trainer"]
    # Comma-split artifact "or Trainer"
    assert "Bike Trainer" in transform_equipment_string("TT Bike, or Trainer")


def test_decompose_slash_string_kayak_packraft():
    out = transform_equipment_string("Kayak / Packraft")
    assert out == ["Kayak", "Packraft"]


def test_decompose_three_way_slash():
    out = transform_equipment_string("Kayak / Canoe / Packraft")
    assert out == ["Kayak", "Canoe", "Packraft"]


def test_or_treated_as_slash():
    out = transform_equipment_string("Bench or Box")
    assert out == ["Bench", "Plyo Box"]


def test_rollup_climbing_roped():
    out = transform_equipment_string("Climbing Rope, Belay Device, Carabiners")
    assert out == ["Climbing — roped"]


def test_rollup_bouldering():
    out = transform_equipment_string("Bouldering Shoes, Crash Pad")
    assert out == ["Bouldering"]


def test_rollup_touring_at_ski():
    out = transform_equipment_string("Touring Skis, Climbing Skins, Ski Crampons")
    assert out == ["Touring/AT ski setup"]


def test_rollup_whitewater():
    out = transform_equipment_string(
        "Spray Skirt, Whitewater Helmet, Whitewater PFD, Throw Bag"
    )
    assert out == ["Whitewater paddling setup"]


def test_ambiguous_crampons_in_ski_context():
    # In ski context: route to Touring/AT ski setup
    out = transform_equipment_string("Touring Skis, Crampons")
    assert out == ["Touring/AT ski setup"]


def test_ambiguous_crampons_default_to_mountaineering():
    # No ski context: route to Mountaineering
    out = transform_equipment_string("Crampons, Mountaineering Boots")
    assert out == ["Mountaineering"]


def test_drop_race_fueling_tokens():
    out = transform_equipment_string("Backpack, Gels, Soft Flask")
    assert out == ["Backpack"]


def test_dedupe_preserves_order():
    # Multiple sub-components rolling up to same toggle dedupe to a single
    # canonical token, keeping the order they first appeared.
    out = transform_equipment_string(
        "Climbing Rope, Bouldering Shoes, Carabiners, Crash Pad"
    )
    assert out == ["Climbing — roped", "Bouldering"]


def test_validate_against_canonical_match():
    canon = ["Barbell", "Dumbbell", "Kettlebell"]
    assert validate_against_canonical("Barbell", canon) == "match"
    assert validate_against_canonical("barbell", canon) == "match"
    assert validate_against_canonical("dumbbells", canon) == "unknown"


def test_validate_unknown():
    canon = ["Barbell"]
    assert validate_against_canonical("Trapeze", canon) == "unknown"


def test_empty_input():
    assert transform_equipment_string("") == []
    assert transform_equipment_string(None) == []


# ---------------------------------------------------------------------------
# split_contraindicated_string tests
# ---------------------------------------------------------------------------

from etl.layer0.vocabulary_transforms import split_contraindicated_string


def test_split_body_part_only():
    bp, cond = split_contraindicated_string("Knee, Lower back")
    assert bp == ["Knee", "Lower back"]
    assert cond == []


def test_split_systemic_only():
    bp, cond = split_contraindicated_string("Cardiac, Cognitive")
    assert bp == []
    assert set(cond) == {"Cardiac", "Cognitive"}


def test_split_mixed():
    bp, cond = split_contraindicated_string("Shoulder, Cardiac, Knee, Cognitive")
    assert bp == ["Shoulder", "Knee"]
    assert set(cond) == {"Cardiac", "Cognitive"}


def test_split_drops_grip():
    bp, cond = split_contraindicated_string("Wrist, Grip, Elbow")
    assert bp == ["Wrist", "Elbow"]
    assert cond == []


def test_split_renames_tricep_bicep():
    bp, cond = split_contraindicated_string("Tricep, Bicep")
    assert "Triceps" in bp
    assert "Biceps" in bp
    assert "Tricep" not in bp
    assert "Bicep" not in bp


def test_split_new_body_parts():
    bp, cond = split_contraindicated_string("TFL, Trapezius, Diaphragm, Thumb, Trachea")
    assert set(bp) == {"TFL", "Trapezius", "Diaphragm", "Thumb", "Trachea"}
    assert cond == []


def test_split_slash_decompose_with_condition():
    # Cognitive/Cardiac should decompose and both route to conditions
    bp, cond = split_contraindicated_string("Cognitive/Cardiac")
    assert bp == []
    assert set(cond) == {"Cognitive", "Cardiac"}


def test_split_empty_input():
    assert split_contraindicated_string(None) == ([], [])
    assert split_contraindicated_string("") == ([], [])


def test_split_deduplication():
    bp, cond = split_contraindicated_string("Knee, Knee, Cardiac, Cardiac")
    assert bp == ["Knee"]
    assert cond == ["Cardiac"]


def test_split_sciatica_renames_to_neurological():
    # Sciatica is a nerve-root condition, not a body part — alias to the
    # canonical Neurological category so the contraindicated_conditions
    # validator matches against health_condition_categories.
    bp, cond = split_contraindicated_string("Lower back, Sciatica")
    assert bp == ["Lower back"]
    assert "Neurological" in cond
    assert "Sciatica" not in cond


def test_split_lungs_renames_to_respiratory():
    bp, cond = split_contraindicated_string("Lungs")
    assert bp == []
    assert cond == ["Respiratory"]


def test_split_drops_gear_and_thermal_tokens():
    # Saddle / Goggle / Blister are gear-fit adaptations (Vocab Audit §2.2
    # excluded list); Core Temperature is captured by the Thermoregulation
    # category but the raw token is dropped from contraindications.
    bp, cond = split_contraindicated_string(
        "Saddle, Goggle, Blister, Core Temperature, Knee"
    )
    assert bp == ["Knee"]
    assert cond == []
