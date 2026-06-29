"""Injury-form vocab + per-body-part constraint mapping invariants.

Locks the 2026-05-25 injury-form refresh (#4 + #6): the movement-constraint
vocab fold and the BODY_PART_CONSTRAINTS swap-on-change mapping. Pure-vocab
module (athlete.py imports only typing), so no Flask/DB/circular-import setup.
"""

from athlete import BODY_PART_CONSTRAINTS, KNOWN_MOVEMENT_CONSTRAINTS

# Side-less canonical body parts the injury form filters on — the #255 canonical
# 51 (layer0.body_parts.canonical_name, side-less; plural Biceps/Triceps per live
# exercise data; Abdomen dropped as non-canonical). Kept here rather than imported
# because routes.injuries pulls Flask; a separate test cross-checks the picker.
CANONICAL_PARTS = {
    # Head / Neck
    "Neck", "Jaw", "Trapezius",
    # Shoulder
    "Shoulder", "Rotator cuff", "AC joint", "Shoulder blade", "Collarbone",
    # Arm
    "Elbow", "Forearm", "Wrist", "Hand", "Biceps", "Triceps", "Fingers",
    "Thumb", "Finger pulley", "DIP joint", "CMC joint",
    # Back
    "Upper back", "Lower back", "Spine (general)", "SI joint", "Sciatica",
    # Hip
    "Hip", "Groin", "Hip flexor", "Glute", "Hip crest (iliac crest)", "TFL",
    # Upper leg
    "Quad", "Hamstring", "IT band",
    # Knee
    "Knee", "Kneecap", "Meniscus", "ACL", "PCL", "MCL", "LCL",
    # Lower leg
    "Calf", "Soleus", "Shin", "Achilles", "Peroneal",
    # Foot / Ankle
    "Ankle", "Plantar fascia", "Foot", "Toes",
    # Trunk
    "Rib", "Chest",
}


class TestVocabFold:
    def test_wrist_extension_folded_out(self):
        assert "Pain with wrist extension" not in KNOWN_MOVEMENT_CONSTRAINTS

    def test_fold_target_present(self):
        assert "Pain above specific joint angle" in KNOWN_MOVEMENT_CONSTRAINTS

    def test_enumeration_is_ten(self):
        assert len(KNOWN_MOVEMENT_CONSTRAINTS) == 10
        assert len(set(KNOWN_MOVEMENT_CONSTRAINTS)) == 10


class TestBodyPartConstraints:
    def test_covers_every_canonical_part(self):
        assert set(BODY_PART_CONSTRAINTS) == CANONICAL_PARTS

    def test_every_value_is_known_vocab(self):
        vocab = set(KNOWN_MOVEMENT_CONSTRAINTS)
        for part, constraints in BODY_PART_CONSTRAINTS.items():
            unknown = [c for c in constraints if c not in vocab]
            assert not unknown, f"{part} references non-vocab: {unknown}"

    def test_no_duplicate_constraints_per_part(self):
        for part, constraints in BODY_PART_CONSTRAINTS.items():
            assert len(constraints) == len(set(constraints)), part

    def test_other_catch_all_retired(self):
        # 'Other' was removed from the injury-form vocab (2026-06): the
        # structured body_part field is now closed over the canonical parts so
        # it can't produce a Layer 2D body_part_vocab_miss. No catch-all option.
        assert "Other" not in BODY_PART_CONSTRAINTS

    def test_no_sided_or_legacy_names(self):
        # #255 — the picker is side-less canonical: no 'Left '/'Right ' prefixes,
        # and the back labels use the canonical lowercase 'back'.
        for part in BODY_PART_CONSTRAINTS:
            assert not part.startswith(("Left ", "Right ")), part
        assert "Lower Back" not in BODY_PART_CONSTRAINTS
        assert "Upper Back" not in BODY_PART_CONSTRAINTS


class TestPickerMatchesConstraintMap:
    def test_groups_flatten_to_constraint_keys(self):
        # The form picker (routes.injuries BODY_PART_GROUPS) and the constraint
        # map must stay in lockstep — every selectable part has a constraint set,
        # and no constraint key is unreachable from the picker.
        from routes.injuries import BODY_PART_GROUPS
        picker = [p for _region, parts in BODY_PART_GROUPS for p in parts]
        assert len(picker) == len(set(picker)), "duplicate part in picker"
        assert set(picker) == set(BODY_PART_CONSTRAINTS)
