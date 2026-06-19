"""Injury-form vocab + per-body-part constraint mapping invariants.

Locks the 2026-05-25 injury-form refresh (#4 + #6): the movement-constraint
vocab fold and the BODY_PART_CONSTRAINTS swap-on-change mapping. Pure-vocab
module (athlete.py imports only typing), so no Flask/DB/circular-import setup.
"""

from athlete import BODY_PART_CONSTRAINTS, KNOWN_MOVEMENT_CONSTRAINTS

# Side-less canonical body parts the injury form filters on (routes.injuries
# BODY_PARTS strips Left/Right before lookup). Kept here rather than imported
# because routes.injuries pulls Flask.
CANONICAL_PARTS = {
    "Hand", "Wrist", "Elbow", "Shoulder", "Knee", "Ankle", "Foot", "Hip",
    "Hamstring", "Quad", "Groin", "Abdomen", "Lower Back", "Upper Back",
    "Neck",
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
