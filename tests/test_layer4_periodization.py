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


# ─── ramp_modulation_for (#424 — 3A coupling) ────────────────────────────────


def _l3a(direction="steady", zone=None, workouts=30):
    """Fake Layer3APayload: the modulation reader only touches
    recent_trajectory.medium_term.direction, recent_trajectory.acwr_status.
    combined.zone, and data_density.recent_workouts_count."""
    combined = SimpleNamespace(zone=zone) if zone is not None else None
    return SimpleNamespace(
        recent_trajectory=SimpleNamespace(
            medium_term=SimpleNamespace(direction=direction),
            acwr_status=SimpleNamespace(combined=combined),
        ),
        data_density=SimpleNamespace(recent_workouts_count=workouts),
    )


def test_modulation_none_is_neutral():
    assert pz.ramp_modulation_for(None) == pz.NEUTRAL_MODULATION
    # A steady, data-rich, sweet-spot athlete also lands on the v1 curve.
    assert pz.ramp_modulation_for(_l3a("steady", "sweet_spot", 30)) == (
        pz.NEUTRAL_MODULATION
    )


def test_modulation_building_steepens_ramp():
    mod = pz.ramp_modulation_for(_l3a(direction="building"))
    assert mod.ramp_step_factor > 1.0
    assert mod.deload_multiplier == pz._M_DELOAD  # not a fatigue signal


def test_modulation_fatigue_gentler_ramp_and_deeper_deload():
    mod = pz.ramp_modulation_for(_l3a(direction="fatigued"))
    assert mod.ramp_step_factor < 1.0
    assert mod.deload_multiplier < pz._M_DELOAD  # deload deepened


def test_modulation_sparse_data_gentler_ramp():
    very = pz.ramp_modulation_for(_l3a(workouts=3)).ramp_step_factor
    sparse = pz.ramp_modulation_for(_l3a(workouts=8)).ramp_step_factor
    dense = pz.ramp_modulation_for(_l3a(workouts=30)).ramp_step_factor
    assert very < sparse < dense == 1.0


def test_modulation_acwr_caps_and_deepens():
    nfo = pz.ramp_modulation_for(_l3a(zone="non_functional_overreach"))
    fo = pz.ramp_modulation_for(_l3a(zone="functional_overreach"))
    assert nfo.ramp_step_factor < fo.ramp_step_factor < 1.0
    # Only the non-functional zone forces a deeper deload.
    assert nfo.deload_multiplier < pz._M_DELOAD
    assert fo.deload_multiplier == pz._M_DELOAD


def test_modulation_factor_clamped():
    # Even stacked gentling signals stay within the clamp band (slope > 0).
    mod = pz.ramp_modulation_for(
        _l3a(direction="fatigued", zone="non_functional_overreach", workouts=1)
    )
    assert pz._K_CLAMP[0] <= mod.ramp_step_factor <= pz._K_CLAMP[1]
    assert mod.deload_multiplier >= pz._DELOAD_DEEPEST


def test_modulation_preserves_volume_neutrality():
    # The whole point of scaling the SLOPE (not levels): Base/Build/Peak stay
    # volume-neutral under any modulation.
    for mod in (
        pz.ramp_modulation_for(_l3a(direction="building")),
        pz.ramp_modulation_for(_l3a(direction="fatigued")),
        pz.ramp_modulation_for(
            _l3a(direction="fatigued", zone="non_functional_overreach", workouts=2)
        ),
    ):
        for phase in ("Base", "Build", "Peak"):
            for weeks in (4, 6, 8):
                m = pz.phase_week_multipliers(phase, weeks, 1, "standard", mod)
                assert abs(sum(m) / weeks - 1.0) < 1e-9, (phase, weeks, mod)


def test_log_ramp_modulation_defensive(capsys):
    pz.log_ramp_modulation(None)  # no payload → no line
    assert capsys.readouterr().out == ""
    pz.log_ramp_modulation(_l3a(direction="building", zone="sweet_spot", workouts=20))
    assert "ramp_modulation:" in capsys.readouterr().out


def test_modulation_threads_through_for_phase():
    ps = _ps([("Base", 8)])
    building = pz.phase_week_multipliers_for_phase(ps, "Base", _l3a("building"))
    fatigued = pz.phase_week_multipliers_for_phase(ps, "Base", _l3a("fatigued"))
    neutral = pz.phase_week_multipliers_for_phase(ps, "Base")
    # Steeper ramp → a wider week-1-to-week-3 spread than the neutral curve;
    # gentler ramp → narrower. (Both volume-neutral, so the peak rises/falls.)
    assert (building[2] - building[0]) > (neutral[2] - neutral[0])
    assert (fatigued[2] - fatigued[0]) < (neutral[2] - neutral[0])


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
