"""Tests for D-73 Phase 2.4-Prep — Layer 2C data substrate.

Phase 2.4 (Layer 2C equipment mapper) implementation is queued for the next
session per Andy's 2026-05-19 scope pick (Split: Prep PR first, then 2C).
This Prep PR ships the on-disk substrate Layer 2C will read:

- `layer0.exercises.equipment_substitutes_structured JSONB` — CNF-structured
  substitutes from `etl/sources/parsed_substitutes.json`; Layer 2C §5.4
  Tier 2 resolution.
- `layer0.exercises.terrain_required TEXT[]` — terrain tokens routed via
  `vocabulary_transforms.transform_equipment_string`; Layer 2C §7
  pass-through.
- `layer0.sport_specific_gear_toggles.also_satisfies TEXT[]` — transitive
  implication chains (Layer 2C §6); single v1 case (`Climbing — roped`
  also-satisfies `Rappelling / abseiling`).
- `layer0.sport_specific_gear_toggles.gated_discipline_ids TEXT[]` — reverse
  toggle mapping for §8.3 coaching flag; Andy 2026-05-19 picked structured
  column over hard-coded mapping (DP2 (b)).

The ETL-extractor parser tests (gear-toggle / parsed-substitutes) retired with
`etl/layer0/extractors/` in the 2026-06-11 xlsx-authoring freeze; what remains
here are the on-disk substrate sanity checks (`schema.sql` columns + the toggle
migration) + a smoke check that the shipped `Layer2CPayload` still constructs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


class TestSchemaSubstrate:
    """Verifies the four new columns are declared in the Layer 0 baseline
    snapshot (`etl/output/layer0_etl_v*.sql`, the canonical schema for fresh DB
    init since the v1.7.0 collapse) + the migration SQL for the toggle columns
    exists. These are sanity checks, not full integration tests — Andy
    operationally applies the migrations against Neon per the closing handoff §5
    sequence."""

    SCHEMA_PATH = max(
        (Path(__file__).parent.parent / "etl" / "output").glob("layer0_etl_v*.sql"),
        key=lambda p: tuple(
            int(x) for x in re.search(r"v(\d+)\.(\d+)\.(\d+)", p.name).groups()
        ),
    )
    MIGRATION_PATH = (
        Path(__file__).parent.parent
        / "aidstation-sources"
        / "archive"
        / "etl-scratch"
        / "migrations"
        / "migrate_toggles_v3_columns.sql"
    )

    def test_schema_declares_terrain_required_on_exercises(self):
        text = self.SCHEMA_PATH.read_text()
        assert "terrain_required" in text
        # Column lands on layer0.exercises (not somewhere else).
        ex_block_start = text.index("CREATE TABLE layer0.exercises")
        ex_block_end = text.index(");", ex_block_start)
        assert "terrain_required" in text[ex_block_start:ex_block_end]

    def test_schema_declares_substitutes_structured_on_exercises(self):
        text = self.SCHEMA_PATH.read_text()
        ex_block_start = text.index("CREATE TABLE layer0.exercises")
        ex_block_end = text.index(");", ex_block_start)
        block = text[ex_block_start:ex_block_end]
        assert "equipment_substitutes_structured" in block

    def test_schema_declares_also_satisfies_and_gated_on_toggles(self):
        text = self.SCHEMA_PATH.read_text()
        tog_start = text.index(
            "CREATE TABLE layer0.sport_specific_gear_toggles"
        )
        tog_end = text.index(");", tog_start)
        block = text[tog_start:tog_end]
        assert "also_satisfies" in block
        assert "gated_discipline_ids" in block

    def test_toggle_migration_carries_climbing_population(self):
        text = self.MIGRATION_PATH.read_text()
        # All three known cases UPDATEd in the migration.
        assert "'Climbing — roped'" in text
        assert "'Rappelling / abseiling'" in text
        assert "'Snowshoeing setup'" in text
        # CNF shape for Climbing also_satisfies — single rappelling entry.
        assert "ARRAY['Rappelling / abseiling']" in text
        # D-012 / D-013 / D-017 gated_discipline_ids.
        assert "'D-012'" in text
        assert "'D-013'" in text
        assert "'D-017'" in text

    def test_layer2c_payload_still_constructs(self):
        # Layer2CPayload + sub-types shipped 2026-05-17 (§5.6 amendment).
        # Phase 2.4-Prep doesn't touch the payload — this is a regression
        # guard against accidental import-time breakage from the ETL +
        # vocabulary edits in this session.
        from layer4.context import (
            DisciplineCoverage,
            Layer2CCoachingFlag,
            Layer2CPayload,
            ResolutionDetail,
            ResolvedExercise,
        )

        payload = Layer2CPayload(
            locale_id="home",
            etl_version_set={"0A": "v1", "0B": "v19", "0C": "v3"},
            effective_pool=["Barbell", "Dumbbell"],
            discipline_coverage=[
                DisciplineCoverage(
                    discipline_id="D-001",
                    discipline_name="Trail Running",
                    exercise_db_sport="Running",
                    total_exercises=10,
                    tier_1_count=6,
                    tier_2_count=2,
                    tier_3_count=1,
                    unavailable_count=1,
                    coverage_pct=0.9,
                ),
            ],
            exercises_resolved=[
                ResolvedExercise(
                    exercise_id="EX001",
                    exercise_name="Back Squat (Barbell)",
                    exercise_type="strength",
                    discipline_ids=["D-001"],
                    sport_relevance_notes={"D-001": "Primary"},
                    priority_per_discipline={"D-001": "Critical"},
                    tier=1,
                    resolution_detail=None,
                    terrain_required=[],
                    contraindicated_parts=[],
                    contraindicated_conditions=[],
                    accommodations=[],
                ),
            ],
            coaching_flags=[],
        )
        assert payload.locale_id == "home"
        assert payload.exercises_resolved[0].tier == 1
        # ResolutionDetail still optional + still accepts the tier-2 + tier-3 fields.
        rd = ResolutionDetail(
            substitute_text="DB Bench Press",
            substitute_equipment=["Dumbbell", "Bench"],
            is_improvised=False,
        )
        assert rd.substitute_text == "DB Bench Press"
        # Coaching-flag enum is enforced.
        flag = Layer2CCoachingFlag(
            flag_type="low_coverage",
            discipline_id="D-017",
            discipline_name="Snowshoeing",
            affected_exercise_ids=[],
            message="Low coverage",
            metadata={},
        )
        assert flag.flag_type == "low_coverage"
        with pytest.raises(Exception):
            Layer2CCoachingFlag(
                flag_type="not_a_real_flag",
                discipline_id=None,
                discipline_name=None,
                affected_exercise_ids=[],
                message="x",
                metadata={},
            )
