"""Canon coverage + correctness, validated against the real source xlsx.

These tests run the actual `sports_framework` extractors over
`Sports_Framework_v11.xlsx` (no DB needed) and assert that the discipline
canon resolves *every* (id, name) the source produces — so drift can never
silently reappear: a new unmapped variant in the source would fail
`test_every_source_id_is_accounted_for`.
"""
from __future__ import annotations

import os

import openpyxl
import pytest

from etl.layer0 import discipline_canon as dc
from etl.layer0.extractors import sports_framework as sf

_XLSX = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "sources", "Sports_Framework_v11.xlsx"
)


@pytest.fixture(scope="module")
def wb():
    if not os.path.exists(_XLSX):
        pytest.skip(f"source workbook not found: {_XLSX}")
    return openpyxl.load_workbook(_XLSX, data_only=True, read_only=True)


# ---------------------------------------------------------------------------
# Static canon shape
# ---------------------------------------------------------------------------

def test_canon_has_25_disciplines():
    assert len(dc.CANONICAL_NAMES) == 25


def test_merges_and_removals():
    assert dc.resolve_ids("D-005") == ["D-004"]
    assert dc.resolve_ids("D-016") == ["D-004"]
    assert dc.canonical_name("D-004") == "Swimming"
    assert dc.resolve_ids("D-020") == []          # Swimrun -> sport
    assert dc.resolve_ids("D-023") == []          # Ski Transitions -> dropped
    assert "D-005" not in dc.CANONICAL_NAMES
    assert "D-016" not in dc.CANONICAL_NAMES


def test_overlay_corrections():
    assert dc.canonical_name("D-021") == "Uphill Skinning"   # not "Ski Touring"
    assert dc.canonical_name("D-022") == "Alpine Descent"    # not "Alpine Skiing"
    assert dc.canonical_name("D-025") == "Fencing"           # not "Epee Fencing"
    assert dc.canonical_name("D-029") == "Rifle Shooting"    # not "Biathlon Shooting"


def test_composite_split():
    assert dc.resolve_ids("D-006 + D-007") == ["D-006", "D-007"]
    assert dc.resolve_ids("D-010 + D-011") == ["D-010", "D-011"]


def test_pseudo_and_placeholder_ids_are_not_disciplines():
    assert dc.resolve_ids("D-014 (Ref)") == []   # NOT D-014
    assert dc.resolve_ids("-") == []
    assert dc.resolve_ids("—") == []
    assert dc.resolve_ids("") == []
    assert dc.resolve_ids(None) == []


def test_non_discipline_classification():
    assert dc.classify_non_discipline("Strength Training") == dc.CATEGORY_STRENGTH
    assert dc.classify_non_discipline("Mobility / Recovery") == dc.CATEGORY_MOBILITY
    assert dc.classify_non_discipline("Mobility/Recovery") == dc.CATEGORY_MOBILITY
    assert dc.classify_non_discipline("WEEKLY TOTAL TARGET") == dc.CATEGORY_WEEKLY_TOTAL
    # Orphans are NOT kept as non-disciplines -> dropped
    assert dc.classify_non_discipline("Portage Running (*Conditional)") is None
    assert dc.classify_non_discipline("Technical Scrambling (Sky Extreme only)") is None


# ---------------------------------------------------------------------------
# Coverage against the live source workbook
# ---------------------------------------------------------------------------

def _all_source_keys(wb):
    """Every (raw_id, raw_name) the extractors emit across discipline tables."""
    keys: set[tuple[str | None, str | None]] = set()
    for r in sf.extract_disciplines(wb["Discipline Library"]):
        keys.add((r["discipline_id"], r["discipline_name"]))
    for r in sf.extract_sport_discipline_map(wb["Sport × Discipline Map"]):
        keys.add((r["discipline_id"], r["discipline_name"]))
    for r in sf.extract_phase_load_allocation(wb["Phase Load Allocation"]):
        keys.add((r["discipline_id"], r["discipline_name"]))
    for r in sf.extract_discipline_training_gaps(wb):
        keys.add((r["discipline_id"], r["discipline_name"]))
    for r in sf.extract_discipline_substitutes(wb):
        keys.add((r["target_id"], r["target_name"]))
        keys.add((r["substitute_id"], r["substitute_name"]))
    return keys


def test_every_source_id_is_accounted_for(wb):
    """Each raw id either resolves to canonical ids, or is a kept non-discipline,
    or is a known/intentional drop. Nothing falls through unexplained."""
    unexplained: list[tuple] = []
    for raw_id, raw_name in _all_source_keys(wb):
        if dc.resolve_ids(raw_id):
            continue
        if dc.classify_non_discipline(raw_name) is not None:
            continue
        if (raw_id in dc.REMOVED_IDS
                or (raw_id and raw_id.strip() in dc.REMOVED_IDS)):
            continue
        # Known intentional orphan drops.
        nm = (raw_name or "").lower()
        if "portage running" in nm or "technical scrambling" in nm:
            continue
        unexplained.append((raw_id, raw_name))
    assert not unexplained, f"unmapped source discipline keys: {unexplained}"


def test_every_resolved_id_has_a_canonical_name(wb):
    for raw_id, _ in _all_source_keys(wb):
        for cid in dc.resolve_ids(raw_id):
            assert dc.canonical_name(cid), f"{raw_id} -> {cid} has no canonical name"


# ---------------------------------------------------------------------------
# Row-level normalization against the live source workbook
# ---------------------------------------------------------------------------

def test_dimension_collapses_to_25_canonical_rows(wb):
    rows = dc.normalize_dimension_rows(sf.extract_disciplines(wb["Discipline Library"]))
    ids = [r["discipline_id"] for r in rows]
    assert sorted(ids) == sorted(dc.CANONICAL_NAMES)        # exactly the 25
    assert len(ids) == len(set(ids))                        # no dup dims
    for r in rows:
        assert r["discipline_name"] == dc.CANONICAL_NAMES[r["discipline_id"]]


def test_sport_discipline_map_normalized(wb):
    raw = sf.extract_sport_discipline_map(wb["Sport × Discipline Map"])
    rows = dc.normalize_named_rows(raw, unique_fields=("sport_name", "discipline_id"))
    # No removed/placeholder/composite ids survive; all names are canonical.
    for r in rows:
        assert dc.is_canonical_discipline(r["discipline_id"]), r
        assert r["discipline_name"] == dc.CANONICAL_NAMES[r["discipline_id"]]
    # Composite "D-006 + D-007" split: Triathlon now has both atomic legs.
    tri = {r["discipline_id"] for r in rows if r["sport_name"] == "Triathlon"}
    assert {"D-006", "D-007"} <= tri
    # unique (sport, id)
    keys = [(r["sport_name"], r["discipline_id"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_phase_load_keeps_non_disciplines_with_category(wb):
    raw = sf.extract_phase_load_allocation(wb["Phase Load Allocation"])
    rows = dc.normalize_named_rows(
        raw,
        unique_fields=("sport_name", "discipline_name"),
        keep_non_discipline=True,
    )
    cats = {r["row_category"] for r in rows if r.get("row_category")}
    assert cats == {dc.CATEGORY_STRENGTH, dc.CATEGORY_MOBILITY, dc.CATEGORY_WEEKLY_TOTAL}
    for r in rows:
        if r["row_category"] is None:
            assert dc.is_canonical_discipline(r["discipline_id"])
            assert r["discipline_name"] == dc.CANONICAL_NAMES[r["discipline_id"]]
        else:
            assert r["discipline_id"] is None
    # Orphan "Portage Running" is gone.
    assert not any("portage" in (r["discipline_name"] or "").lower() for r in rows)


def test_substitutes_drop_removed_and_self(wb):
    raw = sf.extract_discipline_substitutes(wb)
    rows = dc.normalize_substitute_rows(raw)
    for r in rows:
        assert dc.is_canonical_discipline(r["target_id"]), r
        assert dc.is_canonical_discipline(r["substitute_id"]), r
        assert r["target_id"] != r["substitute_id"]
        assert r["target_name"] == dc.CANONICAL_NAMES[r["target_id"]]
        assert r["substitute_name"] == dc.CANONICAL_NAMES[r["substitute_id"]]
    # D-020 (Swimrun) and D-023 were substitute targets/options -> gone.
    touched = {r["target_id"] for r in rows} | {r["substitute_id"] for r in rows}
    assert "D-020" not in touched and "D-023" not in touched


def test_composite_split_attributes_share_to_primary_leg_only():
    # A composite cycling leg with a 50% race-time share must not duplicate
    # that share onto both legs (would double-count the sport's load).
    rows = [{
        "sport_name": "Triathlon", "discipline_id": "D-006 + D-007",
        "discipline_name": "Road Cycling (+ TT/Tri Bike)", "role": "PRIMARY",
        "race_time_pct_low": 45.0, "race_time_pct_high": 55.0,
        "race_time_pct_text": "Bike: 45-55%",
    }]
    out = dc.normalize_named_rows(
        rows, unique_fields=("sport_name", "discipline_id"),
        share_fields=("race_time_pct_low", "race_time_pct_high", "race_time_pct_text"),
    )
    by_id = {r["discipline_id"]: r for r in out}
    assert set(by_id) == {"D-006", "D-007"}
    # Primary leg keeps the share; secondary leg is zeroed.
    assert (by_id["D-006"]["race_time_pct_low"], by_id["D-006"]["race_time_pct_high"]) == (45.0, 55.0)
    assert by_id["D-006"]["race_time_pct_text"] == "Bike: 45-55%"
    assert (by_id["D-007"]["race_time_pct_low"], by_id["D-007"]["race_time_pct_high"]) == (0.0, 0.0)
    assert by_id["D-007"]["race_time_pct_text"] is None


def test_composite_split_preserves_sport_race_share_total(wb):
    # Real data: Triathlon's total race-time share must be unchanged by the
    # canon (the D-006+D-007 split must not inflate cycling).
    raw = sf.extract_sport_discipline_map(wb["Sport × Discipline Map"])
    canon = dc.normalize_named_rows(
        raw, unique_fields=("sport_name", "discipline_id"),
        share_fields=("race_time_pct_low", "race_time_pct_high", "race_time_pct_text"),
    )

    def mid(r):
        lo, hi = r.get("race_time_pct_low"), r.get("race_time_pct_high")
        if lo is not None and hi is not None:
            return (float(lo) + float(hi)) / 2.0
        return float(lo) if lo is not None else 0.0

    def total(rows, sport):
        return sum(mid(r) for r in rows if r["sport_name"] == sport
                   and not (r.get("applicability") or "").upper().startswith("EXCLUD"))

    for sport in ("Triathlon", "Off-Road / Adventure Multisport (Non-Nav)"):
        assert abs(total(raw, sport) - total(canon, sport)) < 0.01, sport


def test_training_gaps_drops_swimrun(wb):
    raw = sf.extract_discipline_training_gaps(wb)
    rows = dc.normalize_named_rows(raw, unique_fields=("discipline_id",))
    ids = {r["discipline_id"] for r in rows}
    assert "D-020" not in ids               # Swimrun gap removed
    assert ids <= set(dc.CANONICAL_NAMES)
