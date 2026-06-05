"""#335 Phase 2 §10 — the `strength_frequency_band` advisory validator.

Catches the bare/empty-strength regression (Base/Build week with 0 sessions)
and gross over-dosing, as `warning` only (never a blocker — Phase 1 lesson).
Duck-typed payload/sessions: the rule only reads `mode`, `sessions[].kind`, and
`sessions[].phase_metadata.{phase_name,week_in_phase}`.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from layer4.validator import (
    _STRENGTH_SESSIONS_PER_WEEK,
    _rule_strength_frequency_band,
)


def _sess(kind, phase, week):
    return NS(kind=kind, phase_metadata=NS(phase_name=phase, week_in_phase=week))


def _payload(sessions, mode="plan_create"):
    return NS(mode=mode, sessions=sessions)


def test_base_week_with_zero_strength_warns():
    # Base target=2; 0 strength → |0-2|=2 > 1 → the bare-strength regression.
    out = _rule_strength_frequency_band(
        _payload([_sess("cardio", "Base", 1), _sess("cardio", "Base", 1)]), None
    )
    assert len(out) == 1
    assert out[0].rule_name == "strength_frequency_band_Base_w1"
    assert out[0].severity == "warning"


def test_in_band_no_warning():
    # 1 strength in Base (target 2 ±1) is within band.
    assert _rule_strength_frequency_band(
        _payload([_sess("strength", "Base", 1), _sess("cardio", "Base", 1)]), None
    ) == []


def test_taper_zero_tolerated():
    # Taper target 1 ±1 → 0 is in band (the final-week strength drop).
    assert _rule_strength_frequency_band(
        _payload([_sess("cardio", "Taper", 3)]), None
    ) == []


def test_peak_overdose_warns():
    out = _rule_strength_frequency_band(
        _payload([_sess("strength", "Peak", 1) for _ in range(3)]), None
    )
    assert out and out[0].rule_name == "strength_frequency_band_Peak_w1"


def test_per_week_bucketing():
    # Build w1 has 2 (ok), Build w2 has 0 (warn) — bucketed by week_in_phase.
    out = _rule_strength_frequency_band(_payload([
        _sess("strength", "Build", 1), _sess("strength", "Build", 1),
        _sess("cardio", "Build", 2),
    ]), None)
    assert [f.rule_name for f in out] == ["strength_frequency_band_Build_w2"]


def test_single_session_mode_skips():
    assert _rule_strength_frequency_band(
        _payload([_sess("cardio", "Base", 1)], mode="single_session_synthesize"), None
    ) == []


def test_all_failures_are_warnings():
    out = _rule_strength_frequency_band(
        _payload([_sess("cardio", "Build", 1)]), None
    )
    assert out and all(f.severity == "warning" for f in out)


def test_dose_table_matches_design():
    assert _STRENGTH_SESSIONS_PER_WEEK == {"Base": 2, "Build": 2, "Peak": 1, "Taper": 1}
