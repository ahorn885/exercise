"""Tests for the markdown vocabulary parser (etl.layer0.extractors.vocabulary).

Tests are pinned to the actual `etl/sources/Vocabulary_Audit_v2.md` so they
serve as a regression net against future audit edits — if the audit
restructures, these tests fire.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from etl.layer0.extractors.vocabulary import parse_vocabulary_md

SOURCE = Path(__file__).parent.parent / "sources" / "Vocabulary_Audit_v2.md"


@pytest.fixture(scope="module")
def parsed():
    return parse_vocabulary_md(SOURCE)


# ---------------------------------------------------------------------------
# Body parts
# ---------------------------------------------------------------------------

def test_body_parts_total_count(parsed):
    # 50 original + 4 actually-new in v2.1 (Trachea, Biceps, Triceps,
    # Diaphragm). The handoff also instructed adding Thumb, Trapezius, TFL,
    # but those were already present in the audit before v2.1 — they get
    # deduped first-seen-wins by the parser. The handoff's expected total
    # of 57 didn't account for those collisions; 54 is the actual outcome.
    # The section's stated total of 41 in §1 is also wrong; the table
    # contents are the source of truth.
    assert len(parsed["body_parts"]) == 54


def test_body_parts_known_canonicals_present(parsed):
    names = {bp["canonical_name"] for bp in parsed["body_parts"]}
    for required in ["Knee", "Achilles", "IT band", "Plantar fascia",
                     "ACL", "Lower back", "Upper back", "Glute"]:
        assert required in names, f"missing {required!r} in body_parts"


def test_body_parts_regions_match_spec(parsed):
    regions = {bp["body_region"] for bp in parsed["body_parts"]}
    expected = {
        "Head / Neck", "Shoulder", "Arm", "Back", "Hip",
        "Upper leg", "Knee", "Lower leg", "Foot / Ankle", "Trunk",
    }
    assert regions == expected


def test_body_parts_arm_region_includes_climbing_specific(parsed):
    arm_canon = {bp["canonical_name"] for bp in parsed["body_parts"]
                 if bp["body_region"] == "Arm"}
    for required in ["Finger pulley", "DIP joint", "CMC joint"]:
        assert required in arm_canon


# ---------------------------------------------------------------------------
# Health condition categories
# ---------------------------------------------------------------------------

def test_health_categories_count(parsed):
    # Audit §2.2 has 12 system categories (11 originals + Cognitive added
    # in v1.3.1 to cover skill-heavy drill gating for TBI / processing-
    # speed conditions). Spec §4.12.2 says ~21 — wrong; source is the
    # source of truth.
    assert len(parsed["health_condition_categories"]) == 12


def test_health_categories_known_present(parsed):
    names = {c["category_name"] for c in parsed["health_condition_categories"]}
    for required in ["Cardiac", "Respiratory", "Endocrine / Metabolic",
                     "GI", "Neurological", "Cognitive / Mental health",
                     "Cognitive",
                     "Musculoskeletal (chronic, non-injury)", "Skin",
                     "Thermoregulation", "Immune / Autoimmune", "Other"]:
        assert required in names


# ---------------------------------------------------------------------------
# Equipment items
# ---------------------------------------------------------------------------

def test_equipment_count(parsed):
    # 121 = standard categories minus DROPs minus duplicates, plus 9 universal.
    # If the audit grows / shrinks this changes — we pin the count to catch
    # it.
    assert len(parsed["equipment_items"]) == 121


def test_equipment_universal_flag(parsed):
    universal = [e for e in parsed["equipment_items"] if e["is_universal"]]
    names = {e["canonical_name"] for e in universal}
    # Vocab Audit §3 "Assumed Universal" lists 9 items.
    assert len(universal) == 9
    assert "Bodyweight" in names
    assert "Wall" in names
    assert "Doorway" in names


def test_equipment_has_categories(parsed):
    cats = {e["equipment_category"] for e in parsed["equipment_items"]}
    for c in ["Barbells & Bars", "Dumbbells", "Kettlebells",
              "Machines — Cardio", "Bodyweight & Portable Equipment",
              "Sport-Specific — Paddle (top-level vessels — kept individual)",
              "Assumed Universal"]:
        assert c in cats


def test_equipment_dropped_items_absent(parsed):
    # Vocab Audit §5 marks these as "DROP from AR Schema 2.2" — they
    # should never appear in the canonical list.
    names = {e["canonical_name"] for e in parsed["equipment_items"]}
    for dropped in ["Jacob's Ladder", "Compression boots (Normatec)",
                    "Sauna access", "Stretch strap"]:
        assert dropped not in names, f"{dropped!r} should have been dropped"


def test_equipment_dedupe_foam_roller(parsed):
    # Foam roller appears in Vocab Audit §3 under both Bodyweight & Portable
    # and Recovery & Therapy — must dedupe to first-seen (Bodyweight).
    rows = [e for e in parsed["equipment_items"]
            if e["canonical_name"].lower() == "foam roller"]
    assert len(rows) == 1
    assert rows[0]["equipment_category"] == "Bodyweight & Portable Equipment"


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------

def test_terrain_count(parsed):
    # D-73 Phase 5.2 Walkthrough — Bucket C sub-item (k): the 15 Section-K
    # audit rows were retired; terrain_types now ships 17 structured TRN-xxx
    # rows code-side per etl/layer0/extractors/vocabulary.py:_TERRAIN_STRUCTURED_ROWS
    # (mirrors migrate_terrain_types.sql which is now a retired tombstone).
    # Row count bumped 16 → 17 by the Bucket C (f) water-vocab expansion
    # 2026-05-24 (NEW TRN-017 Moving Water).
    assert len(parsed["terrain_types"]) == 17


def test_terrain_ids_unique_and_sequential(parsed):
    ids = sorted(t["terrain_id"] for t in parsed["terrain_types"])
    assert len(ids) == len(set(ids))
    assert ids == [f"TRN-{i:03d}" for i in range(1, 18)]


def test_terrain_known_canonical_names_present(parsed):
    names = {t["canonical_name"] for t in parsed["terrain_types"]}
    for required in [
        "Road / Paved", "Technical Trail", "Mountain / Alpine",
        "Pool", "Flat Water", "Moving Water", "Ocean / Tidal", "Whitewater",
        "Snow / Winter Alpine",
        "Climbing Gym", "Pump Track / Skills Course", "Indoor / Gym",
    ]:
        assert required in names


def test_terrain_structured_fields_populated(parsed):
    expected_keys = {
        "terrain_id", "canonical_name", "category",
        "requires_elevation", "technical_surface", "environment",
        "simulatable", "simulation_note", "notes",
    }
    for row in parsed["terrain_types"]:
        assert set(row.keys()) >= expected_keys
        assert isinstance(row["requires_elevation"], bool)
        assert isinstance(row["technical_surface"], bool)
        assert row["environment"] in {"Outdoor", "Indoor"}
        assert row["simulatable"] in {"full", "partial", "none"}
        assert row["category"] in {"Foot", "Water", "Snow", "Climbing", "MTB", "Gym"}


# ---------------------------------------------------------------------------
# Sport-specific gear toggles
# ---------------------------------------------------------------------------

def test_gear_toggles_count(parsed):
    # Vocab Audit §4.1 — exactly 12 toggles
    assert len(parsed["sport_specific_gear_toggles"]) == 12


def test_gear_toggle_names(parsed):
    names = {t["toggle_name"] for t in parsed["sport_specific_gear_toggles"]}
    for required in ["Touring/AT ski setup", "Classic XC ski setup",
                     "Skate XC ski setup", "Climbing — roped",
                     "Bouldering", "Whitewater paddling setup"]:
        assert required in names


def test_gear_toggle_strips_emphasis_suffix(parsed):
    # Toggle 12 in the audit is "Snowshoeing setup *(retained as note only)*"
    # — the emphasis suffix should be stripped.
    names = {t["toggle_name"] for t in parsed["sport_specific_gear_toggles"]}
    assert "Snowshoeing setup" in names
    assert not any("*(" in n for n in names)
