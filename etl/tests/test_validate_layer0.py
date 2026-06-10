"""Unit tests for the validate_layer0 integrity gate — disposition + waiver
logic only. The validators themselves and the live-DB run are exercised by the
`layer0-gate` CI job (Postgres service + genesis snapshot); these tests feed
synthetic validator-result dicts through the pure evaluate/extract/waiver path
so they need no database."""
from __future__ import annotations

import json

import pytest

from etl.layer0 import validate_layer0 as v


def _clean_results() -> dict[str, dict]:
    """An all-passing result for every registered check."""
    return {
        "substitution_fks": {"errors": []},
        "training_gap_fks": {"errors": []},
        "discipline_canon": {"errors": []},
        "modality_group_orphan": {"orphans": []},
        "sum_to_100": {
            "sport_results": [
                {"sport": "Adventure Racing",
                 "phase_status": {"base": "PASS", "build": "PASS",
                                  "peak": "PASS", "taper": "PASS"}},
            ],
        },
        "vocab_alignment": {"exercise_warnings": [], "sport_warnings": []},
        "contraindicated_conditions": {"warnings": []},
        "default_inclusion": {"errors": []},
    }


def test_clean_results_pass() -> None:
    outcomes = v.evaluate(_clean_results(), {})
    assert not v.gate_failed(outcomes)
    assert all(not o.failed for o in outcomes)
    assert {o.name for o in outcomes} == {c.name for c in v.CHECKS}


def test_registry_has_all_seven_logical_checks() -> None:
    # fk_checks splits into two runners → 8 entries, 7 logical checks.
    assert len(v.CHECKS) == 8
    names = [c.name for c in v.CHECKS]
    assert names.count("substitution_fks") == 1
    assert names.count("training_gap_fks") == 1


def test_fk_violation_fails_the_gate() -> None:
    results = _clean_results()
    results["substitution_fks"] = {
        "errors": [{"target_id": "D-001", "substitute_id": "D-999",
                    "broken": ["substitute_id"]}],
    }
    outcomes = v.evaluate(results, {})
    assert v.gate_failed(outcomes)
    sub = next(o for o in outcomes if o.name == "substitution_fks")
    assert sub.failed
    assert sub.unwaived[0].id == "D-001->D-999"
    assert "dangling FK" in sub.unwaived[0].detail


def test_sum_to_100_waived_passes() -> None:
    results = _clean_results()
    results["sum_to_100"] = {
        "sport_results": [
            {"sport": "Skimo",
             "phase_status": {"base": "WARN", "build": "PASS",
                              "peak": "PASS", "taper": "PASS"}},
        ],
    }
    waivers = {"sum_to_100": {"Skimo"}}
    outcomes = v.evaluate(results, waivers)
    s2 = next(o for o in outcomes if o.name == "sum_to_100")
    assert s2.waived == ["Skimo"]
    assert not s2.unwaived
    assert not s2.failed
    assert not v.gate_failed(outcomes)


def test_sum_to_100_unwaived_fails() -> None:
    results = _clean_results()
    results["sum_to_100"] = {
        "sport_results": [
            {"sport": "Skimo",
             "phase_status": {"base": "WARN", "build": "PASS",
                              "peak": "PASS", "taper": "PASS"}},
        ],
    }
    outcomes = v.evaluate(results, {})
    assert v.gate_failed(outcomes)
    s2 = next(o for o in outcomes if o.name == "sum_to_100")
    assert s2.unwaived[0].id == "Skimo"
    assert "base" in s2.unwaived[0].detail


def test_waiver_only_suppresses_matching_check() -> None:
    # A sum_to_100 waiver must NOT suppress an identically-named violation in
    # another check.
    results = _clean_results()
    results["modality_group_orphan"] = {"orphans": ["Skimo"]}
    outcomes = v.evaluate(results, {"sum_to_100": {"Skimo"}})
    orphan = next(o for o in outcomes if o.name == "modality_group_orphan")
    assert orphan.failed
    assert v.gate_failed(outcomes)


def test_extractors_produce_expected_ids() -> None:
    assert v._v_training_gap_fks(
        {"errors": [{"discipline_id": "D-012", "discipline_name": "Rock Climbing",
                     "gap_type": "no_substitute"}]}
    )[0].id == "D-012"
    assert v._v_discipline_canon(
        {"errors": [{"table": "layer0.disciplines", "column": "discipline_id",
                     "discipline_id": "D-99", "discipline_name": "Z",
                     "problem": "non-canonical id"}]}
    )[0].id == "layer0.disciplines.discipline_id:D-99"
    assert v._v_modality_group_orphan({"orphans": ["D-007"]})[0].id == "D-007"
    assert v._v_vocab_alignment(
        {"exercise_warnings": [{"exercise_id": "E-1", "exercise_name": "x",
                                "unknown_parts": ["Toe"]}],
         "sport_warnings": [{"sport_name": "Foo", "exercise_count": 3,
                             "candidates": []}]}
    ) == [v.Violation("exercise:E-1", "unknown contraindicated body part(s): ['Toe']"),
          v.Violation("sport:Foo", "sport name absent from sport_discipline_bridge (3 exercises)")]
    assert v._v_contraindicated(
        {"warnings": [{"exercise_id": "E-2", "exercise_name": "y",
                       "unknown_conditions": ["Bar"]}]}
    )[0].id == "exercise:E-2"
    assert v._v_default_inclusion(
        {"errors": [{"sport_name": "Adventure Racing", "discipline_id": "D-001",
                     "discipline_name": "Trail Running", "default_inclusion": "maybe"}]}
    )[0].id == "Adventure Racing/D-001"


def test_load_waivers_parses_registry(tmp_path) -> None:
    p = tmp_path / "waivers.json"
    p.write_text(json.dumps({"waivers": [
        {"check": "sum_to_100", "id": "Skimo", "reason": "by design",
         "added": "2026-06-10", "by": "andy"},
        {"check": "sum_to_100", "id": "Swimrun", "reason": "by design",
         "added": "2026-06-10", "by": "andy"},
    ]}), encoding="utf-8")
    waivers = v.load_waivers(p)
    assert waivers == {"sum_to_100": {"Skimo", "Swimrun"}}


def test_load_waivers_missing_file_is_empty(tmp_path) -> None:
    assert v.load_waivers(tmp_path / "nope.json") == {}


def test_shipped_registry_is_valid_and_empty() -> None:
    # The committed registry parses and (per genesis) carries no waivers yet.
    waivers = v.load_waivers(v.WAIVERS_PATH)
    assert waivers == {}


def test_format_report_json_shape() -> None:
    results = _clean_results()
    results["default_inclusion"] = {
        "errors": [{"sport_name": "AR", "discipline_id": "D-1",
                    "discipline_name": "x", "default_inclusion": "maybe"}],
    }
    outcomes = v.evaluate(results, {})
    report = json.loads(v.format_report(outcomes, as_json=True))
    assert report["gate"] == "fail"
    di = next(c for c in report["checks"] if c["name"] == "default_inclusion")
    assert di["unwaived"] == 1
    assert di["failing_ids"] == ["AR/D-1"]


def test_format_report_text_clean() -> None:
    text = v.format_report(v.evaluate(_clean_results(), {}))
    assert "RESULT: PASS" in text
