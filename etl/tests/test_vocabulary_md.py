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
    # Audit §1 enumerates 50 entries across 10 body regions, even though
    # the section's stated total of 41 is wrong — the table contents are
    # the source of truth.
    assert len(parsed["body_parts"]) == 50


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
    # Audit §2.2 has 11 system categories. Spec §4.12.2 says ~21 — wrong;
    # source is the source of truth.
    assert len(parsed["health_condition_categories"]) == 11


def test_health_categories_known_present(parsed):
    names = {c["category_name"] for c in parsed["health_condition_categories"]}
    for required in ["Cardiac", "Respiratory", "Endocrine / Metabolic",
                     "GI", "Neurological", "Cognitive / Mental health",
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
    # 15 distinct Section K labels per spec §4.12.4
    assert len(parsed["terrain_types"]) == 15


def test_terrain_canonical_uses_section_k_labels(parsed):
    names = {t["canonical_name"] for t in parsed["terrain_types"]}
    # Section K labels are the right column of the audit terrain table
    for required in ["Hill / mountain access", "Trail access",
                     "Whitewater access", "Snow terrain"]:
        assert required in names


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
