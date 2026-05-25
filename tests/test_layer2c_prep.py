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

Tests cover the ETL extractor changes + a smoke check that the existing
shipped `Layer2CPayload` still constructs (since the Prep PR doesn't touch
the payload shape, this is just confirming nothing rotted).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etl.layer0.extractors.exercise_db import (
    load_parsed_substitutes_structured,
)
from etl.layer0.extractors.vocabulary import (
    _TOGGLE_ALSO_SATISFIES,
    _TOGGLE_GATED_DISCIPLINES,
    _parse_gear_toggles,
)


# ─── Vocabulary parser — toggle metadata ────────────────────────────────────


# Minimal §4.1 markdown fixture that exercises 3 of the 12 canonical toggles.
# Schema mirrors the real Vocabulary_Audit_v2.md table shape: header pipe-row,
# separator pipe-row, then one row per toggle.
_TOGGLES_MD_FIXTURE = """
## 4.1 The 12 toggles

| # | Toggle (canonical token) | Replaces these former col 7 sub-tokens | Used by |
|---|--------------------------|-----------------------------------------|---------|
| 4 | Climbing — roped | Climbing rope, Harness, Belay device | Lead climbing, top-rope |
| 6 | Rappelling / abseiling | Rappel device, Harness | Fixed-rope descent, AR abseil |
| 12 | Snowshoeing setup *(retained as note only)* | (Snowshoes already top-level singleton) | — |

## 4.2 Notes on overlap and edge cases
"""


class TestGearToggleParser:
    """Verifies `_parse_gear_toggles` attaches `also_satisfies` +
    `gated_discipline_ids` per the code-side mappings."""

    def test_climbing_roped_also_satisfies_rappelling(self):
        rows = _parse_gear_toggles(_TOGGLES_MD_FIXTURE)
        climbing = next(r for r in rows if r["toggle_name"] == "Climbing — roped")
        assert climbing["also_satisfies"] == ["Rappelling / abseiling"]
        assert climbing["gated_discipline_ids"] == ["D-012"]

    def test_rappelling_gates_d011_no_also_satisfies(self):
        rows = _parse_gear_toggles(_TOGGLES_MD_FIXTURE)
        rappel = next(
            r for r in rows if r["toggle_name"] == "Rappelling / abseiling"
        )
        assert rappel["also_satisfies"] == []
        assert rappel["gated_discipline_ids"] == ["D-013"]

    def test_snowshoeing_setup_emphasis_stripped_and_gates_d015(self):
        rows = _parse_gear_toggles(_TOGGLES_MD_FIXTURE)
        snow = next(r for r in rows if r["toggle_name"] == "Snowshoeing setup")
        assert snow["also_satisfies"] == []
        assert snow["gated_discipline_ids"] == ["D-017"]

    def test_unknown_toggle_gets_empty_lists(self):
        # An imaginary toggle not in either code-side dict should land with
        # empty `also_satisfies` + `gated_discipline_ids` lists.
        md = (
            "## 4.1 The 12 toggles\n\n"
            "| # | Toggle (canonical token) | Replaces these former col 7 sub-tokens | Used by |\n"
            "|---|--------------------------|----------------------------------------|---------|\n"
            "| 99 | Whitewater paddling setup | Spray skirt, WW helmet | Whitewater |\n\n"
            "## 4.2 Notes on overlap and edge cases\n"
        )
        rows = _parse_gear_toggles(md)
        ww = next(r for r in rows if r["toggle_name"] == "Whitewater paddling setup")
        assert ww["also_satisfies"] == []
        assert ww["gated_discipline_ids"] == []

    def test_paired_equipment_categories_still_empty(self):
        # Phase 2.4-Prep doesn't change `paired_equipment_categories`
        # extraction (still empty per the existing comment — no clean
        # source signal in the markdown). Regression guard.
        rows = _parse_gear_toggles(_TOGGLES_MD_FIXTURE)
        for r in rows:
            assert r["paired_equipment_categories"] == []

    def test_constants_are_self_consistent(self):
        # Every toggle listed in `_TOGGLE_ALSO_SATISFIES` references targets
        # that themselves appear as keys in `_TOGGLE_GATED_DISCIPLINES`
        # (the current single case is `Climbing — roped` → `Rappelling /
        # abseiling`, and `Rappelling / abseiling` is itself a gating
        # toggle). This catches accidental rename drift.
        for _, targets in _TOGGLE_ALSO_SATISFIES.items():
            for target in targets:
                assert target in _TOGGLE_GATED_DISCIPLINES, (
                    f"also_satisfies target {target!r} not in "
                    f"_TOGGLE_GATED_DISCIPLINES — rename drift?"
                )


# ─── Parsed substitutes JSON loader ─────────────────────────────────────────


class TestParsedSubstitutesLoader:
    """Verifies `load_parsed_substitutes_structured` reads the shipped JSON
    + returns a CNF-shaped per-exercise map. Tests assume the bundled
    `etl/sources/parsed_substitutes.json` is intact (154 exercises × 510
    entries per the migration script's docstring)."""

    def test_default_path_loads_known_exercise(self):
        out = load_parsed_substitutes_structured()
        # EX001 is "Back Squat (Barbell)" per the bundled JSON; it has at
        # least one substitute and at least one improvised entry.
        assert "EX001" in out
        ex001 = out["EX001"]
        assert len(ex001) >= 1
        assert all("substitute_text" in s for s in ex001)
        assert all("equipment_required" in s for s in ex001)
        assert all("is_improvised" in s for s in ex001)
        assert any(s["is_improvised"] for s in ex001)

    def test_cnf_shape_is_list_of_lists(self):
        out = load_parsed_substitutes_structured()
        ex001 = out["EX001"]
        for sub in ex001:
            eq = sub["equipment_required"]
            assert isinstance(eq, list)
            for group in eq:
                # Outer-OR-of-inner-AND CNF: each `group` is a list of
                # required-together canonical names.
                assert isinstance(group, list)
                assert all(isinstance(name, str) for name in group)

    def test_missing_path_returns_empty_dict(self, tmp_path):
        bogus = tmp_path / "does_not_exist.json"
        out = load_parsed_substitutes_structured(path=bogus)
        assert out == {}

    def test_custom_path_round_trip(self, tmp_path):
        fixture = tmp_path / "parsed.json"
        fixture.write_text(
            json.dumps([
                {
                    "ex_id": "EXTEST1",
                    "name": "Test Squat",
                    "substitutes": [
                        {
                            "substitute_text": "DB Test Squat",
                            "equipment_required": [["Dumbbell"]],
                            "is_improvised": False,
                        },
                    ],
                },
                {
                    "ex_id": "EXTEST2",
                    "name": "Test Lunge",
                    "substitutes": [],
                },
            ]),
            encoding="utf-8",
        )
        out = load_parsed_substitutes_structured(path=fixture)
        assert set(out.keys()) == {"EXTEST1", "EXTEST2"}
        assert out["EXTEST1"][0]["substitute_text"] == "DB Test Squat"
        assert out["EXTEST2"] == []

    def test_entry_without_ex_id_is_skipped(self, tmp_path):
        # Defensive — if the K-parser ever emits a row without ex_id we'd
        # rather silently skip than KeyError downstream.
        fixture = tmp_path / "parsed.json"
        fixture.write_text(
            json.dumps([
                {"name": "Anonymous", "substitutes": []},
                {"ex_id": "EXTEST3", "name": "Real", "substitutes": []},
            ]),
            encoding="utf-8",
        )
        out = load_parsed_substitutes_structured(path=fixture)
        assert out == {"EXTEST3": []}


# ─── Schema substrate / Layer2CPayload smoke ────────────────────────────────


class TestSchemaSubstrate:
    """Verifies the four new columns are declared in `etl/layer0/schema.sql`
    (canonical schema for fresh DB init) + the migration SQL for the
    toggle columns exists. These are sanity checks, not full integration
    tests — Andy operationally applies the migrations against Neon per the
    closing handoff §5 sequence."""

    SCHEMA_PATH = Path(__file__).parent.parent / "etl" / "layer0" / "schema.sql"
    MIGRATION_PATH = (
        Path(__file__).parent.parent
        / "aidstation-sources"
        / "migrations"
        / "migrate_toggles_v3_columns.sql"
    )

    def test_schema_declares_terrain_required_on_exercises(self):
        text = self.SCHEMA_PATH.read_text()
        assert "terrain_required" in text
        # Column lands on layer0.exercises (not somewhere else).
        ex_block_start = text.index("CREATE TABLE IF NOT EXISTS layer0.exercises")
        ex_block_end = text.index(");", ex_block_start)
        assert "terrain_required" in text[ex_block_start:ex_block_end]

    def test_schema_declares_substitutes_structured_on_exercises(self):
        text = self.SCHEMA_PATH.read_text()
        ex_block_start = text.index("CREATE TABLE IF NOT EXISTS layer0.exercises")
        ex_block_end = text.index(");", ex_block_start)
        block = text[ex_block_start:ex_block_end]
        assert "equipment_substitutes_structured" in block

    def test_schema_declares_also_satisfies_and_gated_on_toggles(self):
        text = self.SCHEMA_PATH.read_text()
        tog_start = text.index(
            "CREATE TABLE IF NOT EXISTS layer0.sport_specific_gear_toggles"
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
