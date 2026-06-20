"""#339 — equivalent-discipline variety carve-out, wired across all 4 paths.

`VARIETY_CARVEOUT_PROMPT_SECTION` is a path-neutral prompt section (like
`CARDIO_PROGRAMMING_PROMPT_SECTION`) gated on the athlete's Coaching-memory
variety preference (#690 surfaced that block onto Layer 1), scoped to easy
foot-based sessions, and self-limiting so it defers to an explicit single-session
sport pick + race-week specificity. It is included in per_phase's SYSTEM_PROMPT
and appended by the plan_refresh / single_session / race_week_brief system
prompts. The durable Coaching-memory render itself was per_phase-only under #690;
#339 extends it to the other three paths (render extension covered in each path's
own prompt test).
"""

import layer4.plan_refresh as pr
import layer4.race_week_brief as rwb
import layer4.single_session as ss
from layer4.per_phase import SYSTEM_PROMPT, VARIETY_CARVEOUT_PROMPT_SECTION


class TestVarietyCarveOutSection:
    def test_gated_on_coaching_memory_variety_pref(self):
        body = VARIETY_CARVEOUT_PROMPT_SECTION
        # fires only on an explicit variety preference in the Coaching-memory block
        assert "ONLY if" in body
        assert "Coaching memory" in body
        # the foot-group equivalence is named concretely (road run <-> trail run)
        assert "road run" in body and "trail run" in body

    def test_preserves_count_long_quality_contract(self):
        low = VARIETY_CARVEOUT_PROMPT_SECTION.lower()
        assert "easy" in low                      # easy-typed sessions only
        assert "long" in low and "quality" in low  # long + quality stay on-discipline
        assert "count" in low                      # counts unchanged

    def test_cross_mode_swaps_excluded(self):
        # bike-for-run (and any cross cardio-mode) swap is out of scope
        assert "do not swap across cardio modes" in VARIETY_CARVEOUT_PROMPT_SECTION.lower()

    def test_self_limiting_guard_defers_to_explicit_requests(self):
        low = VARIETY_CARVEOUT_PROMPT_SECTION.lower()
        # the guard that keeps it inert on the single_session + race_week paths
        assert "never override" in low
        assert "race-week specificity" in low


class TestCarveOutWiredIntoAllFourPaths:
    def test_per_phase_system_prompt_includes_carveout(self):
        assert VARIETY_CARVEOUT_PROMPT_SECTION in SYSTEM_PROMPT

    def test_single_session_system_prompt_includes_carveout(self):
        assert VARIETY_CARVEOUT_PROMPT_SECTION in ss._SYSTEM_PROMPT

    def test_plan_refresh_wires_carveout_and_render(self):
        # plan_refresh appends the section to each tier's system prompt + renders
        # the Coaching-memory block at runtime; assert it shares both symbols.
        assert pr.VARIETY_CARVEOUT_PROMPT_SECTION is VARIETY_CARVEOUT_PROMPT_SECTION
        from layer4.per_phase import _format_coaching_memory
        assert pr._format_coaching_memory is _format_coaching_memory

    def test_race_week_brief_wires_carveout_and_render(self):
        assert rwb.VARIETY_CARVEOUT_PROMPT_SECTION is VARIETY_CARVEOUT_PROMPT_SECTION
        from layer4.per_phase import _format_coaching_memory
        assert rwb._format_coaching_memory is _format_coaching_memory
