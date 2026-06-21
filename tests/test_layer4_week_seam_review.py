"""Tests for the D-77 Slice 3 intra-phase week-seam reviewer.

Covers the new module (`layer4/week_seam_review.py`): the per-week rollup, the
grid-anchored prompt rendering, the verdict/coercion path (reused from the phase
reviewer), and the new cache key (`hashing.compute_week_seam_review_cache_key`).
Coherence itself is only judged on a real-LLM run (design §14) — these tests
pin the mechanics: that the planned-vs-actual framing reaches the prompt and
that the call/cache contract holds.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from layer4.hashing import compute_week_seam_review_cache_key
from layer4.payload import PlanSession
from layer4.seam_review import _SeamReviewerOutput as _SeamOut
from layer4.week_seam_review import (
    compute_week_rollup,
    render_week_seam_prompt,
    review_week_seam,
)

_START = date(2026, 4, 1)
_BAND = (5.0, 8.0)
_INTENSITY = {"Z1-Z2": 0.8, "Z3": 0.15, "Z4-Z5": 0.05}


def _cardio_session(
    *,
    d: date,
    week_in_phase: int,
    idx: int = 0,
    main_min: int = 50,
    main_zone: str = "Z2",
) -> PlanSession:
    """One cardio PlanSession in a given week, with phase_metadata so the
    week-grouping + rollup logic can bucket it."""
    return PlanSession.model_validate(
        {
            "session_id": f"s-{d.isoformat()}-{idx}",
            "plan_version_id": 1,
            "date": d.isoformat(),
            "day_of_week": d.strftime("%a"),
            "session_index_in_day": idx,
            "time_of_day": "morning",
            "kind": "cardio",
            "discipline_id": "D-run",
            "discipline_name": "Running",
            "locale_id": "home",
            "locale_name": "home",
            "duration_min": main_min + 10,
            "intensity_summary": "easy",
            "session_notes": "aerobic.",
            "coaching_intent": "Z2.",
            "coaching_flags": [],
            "phase_metadata": {
                "phase_name": "Build",
                "week_in_phase": week_in_phase,
                "total_weeks_in_phase": 4,
                "intended_volume_band": _BAND,
                "intended_intensity_distribution": _INTENSITY,
            },
            "cardio_blocks": [
                {
                    "block_kind": "main_set",
                    "duration_min": main_min,
                    "intensity_zone": main_zone,
                    "intensity_target": {"hr_bpm_low": 130, "hr_bpm_high": 145},
                    "instructions": "steady.",
                },
                {
                    "block_kind": "cooldown",
                    "duration_min": 10,
                    "intensity_zone": "Z1",
                    "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 120},
                    "instructions": "easy.",
                },
            ],
        }
    )


def _week(week_in_phase: int, *, n_sessions: int, main_min: int = 50, zone: str = "Z2") -> list[PlanSession]:
    base = _START + timedelta(days=(week_in_phase - 1) * 7)
    return [
        _cardio_session(d=base + timedelta(days=2 * i), week_in_phase=week_in_phase, idx=0, main_min=main_min, main_zone=zone)
        for i in range(n_sessions)
    ]


def _stub(verdict: str, *, issues: list[str] | None = None, direction: str | None = None):
    def caller(*_a, **_kw):
        return _SeamOut(
            tool_args={
                "reviewer_verdict": verdict,
                "seam_issues": issues or [],
                "proposed_patch_direction": direction,
            },
            input_tokens=1200,
            output_tokens=80,
            latency_ms=2000,
        )

    return caller


def _review(prior_ss, next_ss, *, prior_mult, next_mult, prior_recovery, next_recovery, caller):
    return review_week_seam(
        phase_name="Build",
        prior_week_in_phase=2,
        next_week_in_phase=3,
        prior_week_sessions=prior_ss,
        next_week_sessions=next_ss,
        prior_planned_multiplier=prior_mult,
        next_planned_multiplier=next_mult,
        prior_is_recovery=prior_recovery,
        next_is_recovery=next_recovery,
        phase_volume_band=_BAND,
        prior_intended_intensity=_INTENSITY,
        next_intended_intensity=_INTENSITY,
        layer2d_payload=None,
        discipline_mix=["D-run"],
        mode="standard",
        race_format="open_ended",
        event_date=None,
        seam_iteration=1,
        prior_seam_issues=[],
        caller=caller,
    )


class TestWeekRollup:
    def test_total_and_zone_split(self):
        # 3 sessions, each 60 min total (50 Z2 + 10 Z1) -> 3.0 hr, all Z1-Z2.
        roll = compute_week_rollup(_week(2, n_sessions=3, main_min=50, zone="Z2"))
        assert roll.session_count == 3
        assert roll.total_hours == pytest.approx(3.0)
        assert roll.z12_hours == pytest.approx(3.0)
        assert roll.z3_hours == pytest.approx(0.0)
        assert roll.z45_hours == pytest.approx(0.0)

    def test_z3_and_z45_buckets(self):
        roll = compute_week_rollup(_week(2, n_sessions=1, main_min=40, zone="Z4"))
        # 40 min Z4 main -> Z4-Z5 bucket; 10 min Z1 cooldown -> Z1-Z2.
        assert roll.z45_hours == pytest.approx(40 / 60.0)
        assert roll.z12_hours == pytest.approx(10 / 60.0)


class TestRenderGridAnchors:
    def test_planned_ratio_and_recovery_label_present(self):
        prompt = render_week_seam_prompt(
            phase_name="Build",
            prior_week_in_phase=2,
            next_week_in_phase=3,
            prior_week_sessions=_week(2, n_sessions=3),
            next_week_sessions=_week(3, n_sessions=2),
            prior_planned_multiplier=1.10,
            next_planned_multiplier=0.55,
            prior_is_recovery=False,
            next_is_recovery=True,
            phase_volume_band=_BAND,
            prior_intended_intensity=_INTENSITY,
            next_intended_intensity=_INTENSITY,
            layer2d_payload=None,
            discipline_mix=["D-run"],
            mode="standard",
            race_format="open_ended",
            event_date=None,
            seam_iteration=1,
            prior_seam_issues=[],
        )
        # The planned week-over-week ratio (0.55/1.10 = 0.50) is the reference.
        assert "PLANNED week-over-week volume change" in prompt
        assert "×0.50" in prompt
        # The recovery week is labelled so a dip reads as planned, not a cliff.
        assert "PLANNED RECOVERY (deload) week" in prompt
        assert "loading week" in prompt

    def test_iteration2_includes_prior_issues(self):
        prompt = render_week_seam_prompt(
            phase_name="Build",
            prior_week_in_phase=2,
            next_week_in_phase=3,
            prior_week_sessions=_week(2, n_sessions=2),
            next_week_sessions=_week(3, n_sessions=2),
            prior_planned_multiplier=1.0,
            next_planned_multiplier=1.0,
            prior_is_recovery=False,
            next_is_recovery=False,
            phase_volume_band=_BAND,
            prior_intended_intensity=_INTENSITY,
            next_intended_intensity=_INTENSITY,
            layer2d_payload=None,
            discipline_mix=["D-run"],
            mode="standard",
            race_format="open_ended",
            event_date=None,
            seam_iteration=2,
            prior_seam_issues=["week 3 must drop toward the planned deload"],
        )
        assert "ITERATION 1 ISSUES" in prompt
        assert "planned deload" in prompt


class TestReviewVerdict:
    def test_planned_deload_dip_approved(self):
        # The model approves a planned recovery week's dip — the happy path.
        res = _review(
            _week(2, n_sessions=4),
            _week(3, n_sessions=2),
            prior_mult=1.10,
            next_mult=0.55,
            prior_recovery=False,
            next_recovery=True,
            caller=_stub("approved"),
        )
        assert res.verdict == "approved"
        assert res.proposed_patch_direction is None

    def test_unjustified_cliff_flagged_major_with_direction(self):
        res = _review(
            _week(2, n_sessions=5),
            _week(3, n_sessions=1),
            prior_mult=1.0,
            next_mult=1.08,
            prior_recovery=False,
            next_recovery=False,
            caller=_stub(
                "flagged_major",
                issues=["week 3 drops 80% on a planned loading week"],
                direction="re_prompt_next",
            ),
        )
        assert res.verdict == "flagged_major"
        assert res.proposed_patch_direction == "re_prompt_next"
        assert res.seam_issues

    def test_invalid_combination_coerced_not_raised(self):
        # `patched` + accept_with_observation is contradictory -> coerced to
        # flagged_major + accept_with_observation (inherited pv=55 behavior).
        res = _review(
            _week(2, n_sessions=3),
            _week(3, n_sessions=3),
            prior_mult=1.0,
            next_mult=1.0,
            prior_recovery=False,
            next_recovery=False,
            caller=_stub("patched", issues=["x"], direction="accept_with_observation"),
        )
        assert res.verdict == "flagged_major"
        assert res.proposed_patch_direction == "accept_with_observation"

    def test_unparseable_verdict_raises(self):
        from layer4.errors import Layer4OutputError

        with pytest.raises(Layer4OutputError):
            _review(
                _week(2, n_sessions=2),
                _week(3, n_sessions=2),
                prior_mult=1.0,
                next_mult=1.0,
                prior_recovery=False,
                next_recovery=False,
                caller=_stub("bogus_verdict"),
            )


class TestCacheKey:
    def _key(self, *, idx: int, prior, next_, model="claude-sonnet-4-6") -> str:
        return compute_week_seam_review_cache_key(
            call_cache_key="CCK",
            week_seam_index=idx,
            prior_week_sessions=prior,
            next_week_sessions=next_,
            model=model,
            max_tokens=1500,
            extended_thinking_budget=2000,
        )

    def test_deterministic(self):
        a = self._key(idx=0, prior=_week(2, n_sessions=3), next_=_week(3, n_sessions=2))
        b = self._key(idx=0, prior=_week(2, n_sessions=3), next_=_week(3, n_sessions=2))
        assert a == b

    def test_varies_by_index_and_sessions(self):
        base = self._key(idx=0, prior=_week(2, n_sessions=3), next_=_week(3, n_sessions=2))
        # Different seam index -> different key.
        assert base != self._key(idx=1, prior=_week(2, n_sessions=3), next_=_week(3, n_sessions=2))
        # Different session content -> different key.
        assert base != self._key(idx=0, prior=_week(2, n_sessions=4), next_=_week(3, n_sessions=2))
        # Different reviewer model -> different key.
        assert base != self._key(
            idx=0, prior=_week(2, n_sessions=3), next_=_week(3, n_sessions=2), model="claude-opus-4-8"
        )
