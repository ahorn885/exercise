"""Tests for the sum_to_100 validator's per-phase HIGH-band thresholds.

The validator runs a SQL query in `run_sum_to_100`, but the threshold logic
itself is exercised through the module-level `PHASE_THRESHOLDS` constant —
we assert the thresholds and the PASS/WARN decision in isolation by
reusing the `_compute_adjusted_stack` core. No DB needed.
"""
from __future__ import annotations

from etl.layer0.validation.sum_to_100 import (
    PHASE_THRESHOLDS,
    PHASES,
    _compute_adjusted_stack,
)


def _row(disc: str, role: str, lows: tuple[float, ...], highs: tuple[float, ...]) -> dict:
    return {
        "discipline_name": disc,
        "role": role,
        "is_conditional": "(*conditional)" in role.lower() or role.lower().strip() == "conditional",
        "is_paddle": disc in {"Packrafting", "Kayaking", "Canoeing", "Sea Kayak", "Rowing", "SUP"},
        "base_low": lows[0],  "base_high": highs[0],
        "build_low": lows[1], "build_high": highs[1],
        "peak_low": lows[2],  "peak_high": highs[2],
        "taper_low": lows[3], "taper_high": highs[3],
    }


def test_phase_thresholds_taper_is_90_others_100():
    assert PHASE_THRESHOLDS["base"] == 100.0
    assert PHASE_THRESHOLDS["build"] == 100.0
    assert PHASE_THRESHOLDS["peak"] == 100.0
    assert PHASE_THRESHOLDS["taper"] == 90.0


def test_taper_91_pct_passes():
    # Mirrors Aquabike's v1.3 numbers (taper HIGH = 91.0). Under the v1.3
    # rule (≥100 everywhere) this would WARN; under v1.3.1 (taper ≥ 90)
    # it must PASS.
    rows = [
        _row("A", "Primary", (40, 50, 50, 30), (50, 60, 60, 41)),
        _row("B", "Primary", (50, 50, 50, 50), (53, 53, 50, 50)),
    ]
    adj = _compute_adjusted_stack(rows)
    assert adj["taper"]["high"] == 91.0
    for phase in PHASES:
        threshold = PHASE_THRESHOLDS[phase]
        assert (adj[phase]["high"] >= threshold) == (
            phase != "taper" or adj["taper"]["high"] >= 90.0
        )


def test_taper_89_pct_warns():
    # Just below the new taper threshold — should still WARN.
    rows = [
        _row("A", "Primary", (40, 50, 50, 30), (50, 60, 60, 39)),
        _row("B", "Primary", (50, 50, 50, 50), (53, 53, 50, 50)),
    ]
    adj = _compute_adjusted_stack(rows)
    assert adj["taper"]["high"] == 89.0
    assert adj["taper"]["high"] < PHASE_THRESHOLDS["taper"]


def test_base_99_pct_warns_under_100_threshold():
    # Base / Build / Peak retain their 100% requirement.
    rows = [_row("A", "Primary", (40, 40, 40, 40), (99, 100, 100, 95))]
    adj = _compute_adjusted_stack(rows)
    assert adj["base"]["high"] == 99.0
    assert adj["base"]["high"] < PHASE_THRESHOLDS["base"]
    assert adj["build"]["high"] >= PHASE_THRESHOLDS["build"]
