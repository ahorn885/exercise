"""Tests for the WHOOP physiological_cycles.csv wellness parser (#767 slice 4).

Fixtures are schema-faithful to WHOOP's documented `physiological_cycles.csv`
header. Column resolution is by normalized-token contains-match, so a second
fixture exercises casing / abbreviation / unit drift. LIVE-VERIFY against a real
export is owed (Rule #14) — these pin the documented schema + the tolerant
matcher, not a real-file byte stream.
"""
import pytest

from whoop_csv_parser import (
    _norm,
    _resolve_columns,
    parse_whoop_physiological_cycles,
)

# Canonical WHOOP header (documented export). Includes the "In bed duration"
# decoy so we prove the parser picks "Asleep duration" for sleep minutes.
_HEADER = (
    "Cycle start time,Cycle end time,Cycle timezone,Recovery score %,"
    "Resting heart rate (bpm),Heart rate variability (ms),Skin temp (celsius),"
    "Blood oxygen %,Day Strain,Energy burned (cal),Max HR (bpm),"
    "Average HR (bpm),Sleep onset,Wake onset,Sleep performance %,"
    "Respiratory rate (rpm),Asleep duration (min),In bed duration (min),"
    "Light sleep duration (min),Deep (SWS) duration (min),REM duration (min),"
    "Awake duration (min),Sleep need (min),Sleep debt (min),"
    "Sleep efficiency %,Sleep consistency %"
)


def _row(
    start="2026-05-19 04:30:00",
    recovery="66",
    rhr="48",
    hrv="72.4",
    strain="12.3",
    perf="88",
    asleep="450",
    in_bed="480",
):
    return (
        f"{start},2026-05-19 12:00:00,UTC-05:00,{recovery},{rhr},{hrv},33.1,"
        f"96,{strain},2200,142,121,2026-05-19 04:31:00,2026-05-19 12:00:00,"
        f"{perf},14.2,{asleep},{in_bed},120,95,110,15,470,20,94,90"
    )


def _csv(*lines: str) -> bytes:
    return ("\n".join([_HEADER, *lines]) + "\n").encode("utf-8")


class TestParseWhoop:
    def test_full_row(self):
        out = parse_whoop_physiological_cycles(_csv(_row()))
        assert len(out) == 1
        r = out[0]
        assert r["date"] == "2026-05-19"
        assert r["total_sleep_min"] == 450.0       # Asleep, NOT In bed (480)
        assert r["hrv_rmssd_ms"] == pytest.approx(72.4)
        assert r["resting_hr"] == 48               # rounded int
        assert isinstance(r["resting_hr"], int)
        assert r["recovery_score"] == 66.0
        assert r["day_strain"] == pytest.approx(12.3)
        assert r["sleep_performance_pct"] == 88.0

    def test_asleep_not_in_bed(self):
        # Distinct asleep vs in-bed durations → parser must take asleep.
        out = parse_whoop_physiological_cycles(_csv(_row(asleep="400", in_bed="500")))
        assert out[0]["total_sleep_min"] == 400.0

    def test_resting_hr_rounded(self):
        out = parse_whoop_physiological_cycles(_csv(_row(rhr="47.6")))
        assert out[0]["resting_hr"] == 48

    def test_multiple_days(self):
        out = parse_whoop_physiological_cycles(
            _csv(
                _row(start="2026-05-19 04:30:00"),
                _row(start="2026-05-20 05:00:00"),
            )
        )
        assert {r["date"] for r in out} == {"2026-05-19", "2026-05-20"}

    def test_one_usable_row_among_blanks(self):
        # A fully-blank-metric row is dropped; a usable row on another day stays.
        out = parse_whoop_physiological_cycles(
            _csv(
                _row(start="2026-05-19 04:30:00", rhr="", hrv="", asleep=""),
                _row(start="2026-05-20 05:00:00"),
            )
        )
        assert [r["date"] for r in out] == ["2026-05-20"]

    def test_zero_and_blank_are_none(self):
        # Non-positive / blank metric cells coerce to None, not 0.
        out = parse_whoop_physiological_cycles(
            _csv(_row(rhr="0", hrv="72", asleep=""))
        )
        r = out[0]
        assert r["resting_hr"] is None
        assert r["total_sleep_min"] is None
        assert r["hrv_rmssd_ms"] == 72.0

    def test_bom_tolerated(self):
        raw = ("﻿" + _HEADER + "\n" + _row() + "\n").encode("utf-8")
        out = parse_whoop_physiological_cycles(raw)
        assert out[0]["resting_hr"] == 48

    def test_tolerant_header_variant(self):
        # Different casing, "HRV (ms)" abbreviation, capitalized units.
        header = (
            "Cycle Start Time,Recovery Score %,Resting Heart Rate (bpm),"
            "HRV (ms),Day Strain,Asleep Duration (Min)"
        )
        body = "2026-06-01 05:00:00,70,46,80.5,11.0,420"
        out = parse_whoop_physiological_cycles((header + "\n" + body + "\n").encode())
        r = out[0]
        assert r["date"] == "2026-06-01"
        assert r["resting_hr"] == 46
        assert r["hrv_rmssd_ms"] == pytest.approx(80.5)
        assert r["total_sleep_min"] == 420.0


class TestRejects:
    def test_empty_bytes(self):
        with pytest.raises(ValueError):
            parse_whoop_physiological_cycles(b"")

    def test_no_date_column(self):
        raw = b"Recovery score %,Resting heart rate (bpm)\n66,48\n"
        with pytest.raises(ValueError):
            parse_whoop_physiological_cycles(raw)

    def test_no_metric_column(self):
        raw = b"Cycle start time,Cycle timezone\n2026-05-19 04:30:00,UTC\n"
        with pytest.raises(ValueError):
            parse_whoop_physiological_cycles(raw)

    def test_header_only_no_rows(self):
        with pytest.raises(ValueError):
            parse_whoop_physiological_cycles(_csv())

    def test_all_rows_unusable(self):
        # Date present but every metric blank on every row → ValueError.
        with pytest.raises(ValueError):
            parse_whoop_physiological_cycles(_csv(_row(rhr="", hrv="", asleep="")))


class TestColumnResolution:
    def test_resolve_picks_asleep_over_in_bed(self):
        idx = _resolve_columns(_HEADER.split(","))
        cols = _HEADER.split(",")
        assert cols[idx["total_sleep_min"]] == "Asleep duration (min)"
        assert cols[idx["hrv_rmssd_ms"]] == "Heart rate variability (ms)"
        assert cols[idx["resting_hr"]] == "Resting heart rate (bpm)"

    def test_norm(self):
        assert _norm("Heart rate variability (ms)") == "heart rate variability ms"
