"""Tests for the terrain_types structural-integrity validator.

`run_terrain_types` queries the DB, but the integrity logic lives in the pure
`check_terrain_rows(rows)` helper — exercised here DB-free (mirrors the
`sum_to_100` test pattern).
"""
from __future__ import annotations

from etl.layer0.validation.terrain_types_check import check_terrain_rows


def _row(tid, name="X"):
    return {"terrain_id": tid, "canonical_name": name}


def test_clean_set_passes():
    rows = [_row("TRN-001", "Road"), _row("TRN-002", "Trail"), _row("TRN-020", "Gravel")]
    r = check_terrain_rows(rows)
    assert r == {
        "rows_checked": 3, "pass_count": 3, "error_count": 0,
        "malformed_ids": [], "duplicate_ids": [], "duplicate_names": [],
    }


def test_malformed_id_caught():
    rows = [_row("TRN-001", "A"), _row("TRN-5", "B"), _row("trn-002", "C"),
            _row("TRN-0012", "D")]
    r = check_terrain_rows(rows)
    assert r["malformed_ids"] == ["TRN-0012", "TRN-5", "trn-002"]
    assert r["duplicate_names"] == []
    assert r["error_count"] == 3


def test_null_id_caught_as_null_token():
    r = check_terrain_rows([_row(None, "Mystery"), _row("TRN-001")])
    assert r["malformed_ids"] == ["<null>"]
    assert r["error_count"] == 1


def test_duplicate_terrain_id_caught():
    rows = [_row("TRN-001", "A"), _row("TRN-001", "B")]
    r = check_terrain_rows(rows)
    assert r["duplicate_ids"] == ["TRN-001"]
    assert r["duplicate_names"] == []
    assert r["error_count"] == 1


def test_duplicate_canonical_name_caught():
    rows = [_row("TRN-001", "Trail"), _row("TRN-002", "Trail")]
    r = check_terrain_rows(rows)
    assert r["duplicate_names"] == ["Trail"]
    assert r["duplicate_ids"] == []
    assert r["error_count"] == 1


def test_empty_set_is_clean():
    assert check_terrain_rows([])["error_count"] == 0


def test_multiple_violation_classes_sum():
    rows = [_row("TRN-001", "A"), _row("TRN-001", "A"), _row("BAD", "B")]
    r = check_terrain_rows(rows)
    assert r["duplicate_ids"] == ["TRN-001"]
    assert r["duplicate_names"] == ["A"]
    assert r["malformed_ids"] == ["BAD"]
    assert r["error_count"] == 3
