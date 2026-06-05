"""Unit tests for the per-week volume periodization grid (`layer4.periodization`).

The grid functions duck-type their structure/session inputs (they read only
`.phases[].phase_name/.weeks`, `.derived_from`, `.phase_metadata`,
`.coaching_flags`), so these tests use lightweight `SimpleNamespace` fakes
rather than constructing full pydantic payloads.
"""

from types import SimpleNamespace

import pytest

from layer4 import periodization as pz


def _ps(phases, derived_from="3b_standard"):
    """Fake PhaseStructure: phases = [(name, weeks), ...]."""
    return SimpleNamespace(
        phases=[SimpleNamespace(phase_name=n, weeks=w) for n, w in phases],
        derived_from=derived_from,
    )


# ─── is_deload_week / cadence ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode,cadence",
    [("standard", 4), ("compressed", 3), ("extended", 5)],
)
def test_deload_cadence_per_mode(mode, cadence):
    assert pz.deload_cadence_weeks(mode) == cadence
    # Deloads land on multiples of the cadence, nothing in between.
    for gw in range(1, 21):
        assert pz.is_deload_week(gw, mode) == (gw % cadence == 0)


def test_custom_mode_never_deloads():
    assert pz.deload_cadence_weeks("custom") is None
    assert not any(pz.is_deload_week(gw, "custom") for gw in range(1, 21))


def test_mode_from_derived_from():
    assert pz.mode_from_derived_from("3b_compressed") == "compressed"
    assert pz.mode_from_derived_from("3b_extended") == "extended"
    # Unknown / override → standard default.
    assert pz.mode_from_derived_from("layer4_override") == "standard"
    assert pz.mode_from_derived_from(None) == "standard"


# ─── phase_week_multipliers (loading phases) ─────────────────────────────────


def test_loading_phase_volume_neutral():
    # Base/Build/Peak multipliers average to 1.0 (phase total preserved).
    for phase in ("Base", "Build", "Peak"):
        for weeks in (1, 2, 3, 4, 6, 8):
            mults = pz.phase_week_multipliers(phase, weeks, 1, "standard")
            assert len(mults) == weeks
            assert abs(sum(mults) / weeks - 1.0) < 1e-9, (phase, weeks)


def test_loading_phase_ramp_and_deload_shape():
    # 8-week Base, standard cadence → deloads at weeks 4 and 8; loading weeks
    # ramp up within each 3-week block; deload weeks are the local minima.
    m = pz.phase_week_multipliers("Base", 8, 1, "standard")
    # Ascending within block 1 (weeks 1–3) and block 2 (weeks 5–7).
    assert m[0] < m[1] < m[2]
    assert m[4] < m[5] < m[6]
    # Deload weeks (index 3, 7) are below every loading week.
    loading = [m[i] for i in (0, 1, 2, 4, 5, 6)]
    assert m[3] < min(loading) and m[7] < min(loading)
    # Coming OUT of a deload returns to baseline, not straight to the prior peak.
    assert m[4] < m[2]


def test_deload_offset_follows_global_week():
    # A Build phase starting at plan-global week 5 (after a 4-week Base) puts the
    # deload on its 4th week (global week 8), not its 1st.
    m = pz.phase_week_multipliers("Build", 4, 5, "standard")
    assert m[3] == min(m)  # week 4 (global 8) is the deload
    assert m[0] > m[3]


# ─── phase_week_multipliers (taper) ──────────────────────────────────────────


def test_taper_is_descent_not_renormalized():
    # Taper rides a Bosquet descent into the race week; NOT volume-neutral.
    assert pz.phase_week_multipliers("Taper", 2, 9, "standard") == [0.60, 0.40]
    assert pz.phase_week_multipliers("Taper", 1, 9, "standard") == [0.40]
    three = pz.phase_week_multipliers("Taper", 3, 9, "standard")
    assert three == [0.75, 0.60, 0.40]
    assert sum(three) / 3 < 1.0  # net volume reduction


# ─── structure-derived helpers ───────────────────────────────────────────────


def test_helpers_derive_from_structure():
    ps = _ps([("Base", 4), ("Build", 4), ("Peak", 2), ("Taper", 2)])
    assert pz.phase_global_start_week(ps, "Base") == 1
    assert pz.phase_global_start_week(ps, "Build") == 5
    assert pz.phase_global_start_week(ps, "Taper") == 11
    assert pz.phase_global_start_week(ps, "Missing") is None
    # Build week 4 == plan-global week 8 → a standard deload.
    assert pz.is_deload_week_for(ps, "Build", 4) is True
    assert pz.is_deload_week_for(ps, "Build", 1) is False
    vec = pz.phase_week_multipliers_for_phase(ps, "Build")
    assert len(vec) == 4 and vec[3] == min(vec)


def test_week_volume_multiplier_graceful_fallback():
    ps = _ps([("Base", 4)])
    # Out-of-range week and absent structure both degrade to 1.0 (flat band).
    assert pz.week_volume_multiplier(ps, "Base", 99) == 1.0
    assert pz.week_volume_multiplier(None, "Base", 1) == 1.0
    assert pz.week_volume_multiplier(ps, "Missing", 1) == 1.0
    # In-range resolves to the grid value.
    assert pz.week_volume_multiplier(ps, "Base", 1) == pytest.approx(
        pz.phase_week_multipliers("Base", 4, 1, "standard")[0]
    )


# ─── stamp_recovery_week ─────────────────────────────────────────────────────


def _sess(phase, week, flags=None):
    return SimpleNamespace(
        phase_metadata=SimpleNamespace(phase_name=phase, week_in_phase=week),
        coaching_flags=list(flags or []),
    )


def test_stamp_recovery_week_marks_deloads_only():
    ps = _ps([("Base", 8)])  # standard → deloads at weeks 4 and 8
    sessions = [_sess("Base", w) for w in (1, 3, 4, 7, 8)]
    pz.stamp_recovery_week(sessions, ps)
    flagged = {s.phase_metadata.week_in_phase for s in sessions if "recovery_week" in s.coaching_flags}
    assert flagged == {4, 8}


def test_stamp_recovery_week_idempotent_and_preserves_other_flags():
    ps = _ps([("Base", 8)])
    s = _sess("Base", 4, flags=["long_slow_distance"])
    pz.stamp_recovery_week([s], ps)
    pz.stamp_recovery_week([s], ps)  # second pass must not duplicate
    assert s.coaching_flags.count("recovery_week") == 1
    assert "long_slow_distance" in s.coaching_flags


def test_stamp_recovery_week_noop_without_structure():
    s = _sess("Base", 4)
    pz.stamp_recovery_week([s], None)
    assert s.coaching_flags == []
