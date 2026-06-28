"""Phase 4 Slice 1 — recovery-aware planning guidance (#196).

Unit-tests the freshness gate + the surfaced 3A fields + the strong-lean wording
in `layer4.recovery_guidance.format_recovery_guidance`, and pins that both refresh
tiers share the one helper (single-sourced wording).
"""

from datetime import datetime

from layer4.context import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DataDensity,
    Layer3APayload,
    Layer3Observation,
    RecentTrajectory,
    TrajectoryWindow,
)
from layer4.recovery_guidance import format_recovery_guidance


def _payload(
    *,
    recent_hrv_count: int = 14,
    recent_sleep_count: int = 14,
    short_dir: str = "fatigued",
    medium_dir: str = "steady",
    per_discipline: dict | None = None,
    observations: list | None = None,
) -> Layer3APayload:
    if per_discipline is None:
        per_discipline = {
            "D-run": ACWREntry(
                acute_load=9.0,
                chronic_load=6.0,
                ratio=1.50,
                zone="non_functional_overreach",  # type: ignore[arg-type]
                units="hours",
            )
        }
    return Layer3APayload(
        user_id=42,
        as_of=datetime(2026, 5, 31, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"layer0": "v7"},
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level="good", confidence="high", reasoning_text="r", evidence_basis=["e"]
            ),
            strength=Assessment(
                level="moderate", confidence="medium", reasoning_text="r", evidence_basis=["e"]
            ),
            weak_links=[],
            skill_assessments={},
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction=short_dir,  # type: ignore[arg-type]
                reasoning_text="HRV down 12% over 5 days",
                evidence_basis=["e"],
            ),
            medium_term=TrajectoryWindow(
                direction=medium_dir,  # type: ignore[arg-type]
                reasoning_text="load flat across the block",
                evidence_basis=["e"],
            ),
            acwr_status=ACWRStatus(per_discipline=per_discipline, combined=None),
            confidence="medium",
        ),
        data_density=DataDensity(
            connected_providers=["coros"],
            integration_data_days=28,
            recent_workouts_count=20,
            recent_sleep_count=recent_sleep_count,
            recent_hrv_count=recent_hrv_count,
            self_report_freshness_days=2,
            section_completeness={"C": 1.0},
        ),
        notable_observations=observations if observations is not None else [],
    )


def _obs(category: str, text: str) -> Layer3Observation:
    return Layer3Observation(
        category=category,  # type: ignore[arg-type]
        text=text,
        evidence_basis=["e"],
        elevates_to_hitl=False,
    )


class TestFreshBlockA:
    def test_fresh_payload_emits_strong_lean_block(self):
        out = "\n".join(
            format_recovery_guidance(
                _payload(
                    observations=[_obs("warning", "resting HR elevated 6bpm vs baseline")]
                )
            )
        )
        assert "=== Recovery state (3A wellness — act on this) ===" in out
        # strong-lean directive present
        assert "PRIORITIZE recovery" in out
        assert "cut" in out and "intensity" in out
        # surfaced-but-previously-hidden fields
        assert "Short-term trajectory: fatigued — HRV down 12% over 5 days" in out
        assert "Medium-term trajectory: steady — load flat across the block" in out
        # per-discipline ACWR surfaced (was only combined before)
        assert "ACWR by discipline:" in out
        assert "D-run: zone=non_functional_overreach, ratio=1.50" in out
        # actionable observation surfaced as a recovery flag
        assert "Recovery flags (3A):" in out
        assert "- (warning) resting HR elevated 6bpm vs baseline" in out
        # LLM-soft framing — not a hard rule
        assert "not a hard\nrule" in out or "not a hard rule" in out

    def test_sleep_only_data_is_still_fresh(self):
        out = "\n".join(
            format_recovery_guidance(_payload(recent_hrv_count=0, recent_sleep_count=3))
        )
        assert "act on this" in out
        assert "PRIORITIZE recovery" in out

    def test_empty_acwr_and_observations_omit_their_sublists(self):
        out = "\n".join(
            format_recovery_guidance(_payload(per_discipline={}, observations=[]))
        )
        assert "act on this" in out
        assert "ACWR by discipline:" not in out
        assert "Recovery flags (3A):" not in out
        # guidance still present
        assert "PRIORITIZE recovery" in out

    def test_only_actionable_observation_categories_surface(self):
        out = "\n".join(
            format_recovery_guidance(
                _payload(
                    observations=[
                        _obs("warning", "W-text"),
                        _obs("data_gap", "G-text"),
                        _obs("opportunity", "O-text"),
                        _obs("data_hygiene", "H-text"),
                    ]
                )
            )
        )
        assert "W-text" in out and "G-text" in out
        assert "O-text" not in out and "H-text" not in out


class TestSurfaceNeutralWording:
    def test_directive_is_surface_neutral(self):
        # Slice 2 (Andy 2026-06-28): the directive is reused verbatim across the
        # refresh tiers AND per_phase / race_week_brief / single_session, so the
        # refresh-specific "in this refresh" framing was genericized to "here".
        out = "\n".join(format_recovery_guidance(_payload()))
        assert "PRIORITIZE recovery here:" in out
        assert "in this refresh" not in out


class TestNoDataBlockB:
    def test_no_recovery_data_emits_do_not_infer_and_no_directive(self):
        out = "\n".join(
            format_recovery_guidance(_payload(recent_hrv_count=0, recent_sleep_count=0))
        )
        assert "Do not infer" in out
        assert "plan the normal\nprogression" in out or "plan the normal progression" in out
        # the strong-lean directive must NOT fire on absent data
        assert "PRIORITIZE recovery" not in out
        assert "act on this" not in out


class TestSingleSourced:
    def test_both_refresh_tiers_share_one_helper(self):
        from layer4 import plan_refresh_t2, plan_refresh_t3, recovery_guidance

        assert (
            plan_refresh_t2.format_recovery_guidance
            is recovery_guidance.format_recovery_guidance
        )
        assert (
            plan_refresh_t3.format_recovery_guidance
            is recovery_guidance.format_recovery_guidance
        )

    def test_slice2_surfaces_share_one_helper(self):
        # Slice 2 — per_phase / race_week_brief / single_session fold in the same
        # helper object (single-sourced wording, no per-surface copy).
        from layer4 import (
            per_phase,
            race_week_brief,
            recovery_guidance,
            single_session,
        )

        assert (
            per_phase.format_recovery_guidance
            is recovery_guidance.format_recovery_guidance
        )
        assert (
            race_week_brief.format_recovery_guidance
            is recovery_guidance.format_recovery_guidance
        )
        assert (
            single_session.format_recovery_guidance
            is recovery_guidance.format_recovery_guidance
        )
