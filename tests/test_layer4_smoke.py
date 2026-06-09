"""Real-LLM smoke parity for the Layer 4 plan-generation cone (#206).

Per the Layer-4 "Step 7" gap: the unit suites for the four Layer 4 entry
points stub the LLM caller, so the cone is never exercised against the real
Anthropic SDK in CI — output-shape regressions surface one-at-a-time in prod
instead. This module closes that gap with one real round-trip per entry point.

Mechanism: each entry point takes an injectable caller that defaults to the
production `_default_llm_caller` when omitted. The stub tests pass a fake
caller; here we reuse those tests' *proven* input fixtures (imported as module
namespaces) and simply omit the caller, so the real Sonnet 4.6 adapter runs.

Gated on `ANTHROPIC_API_KEY` via the `requires_anthropic_api_key` marker, like
the Layer 3A/3B smoke modules — the default `pytest tests/` run skips this
file; it executes only in the key-gated CI smoke job.

Assertions are deliberately loose (payload validates, metadata stamped, tokens
counted, sessions present) — shape, not specific reasoning.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import requires_anthropic_api_key

# Reuse the proven per-entry-point fixtures from the stubbed unit suites.
import test_layer4_single_session as ss
import test_layer4_plan_create as pc
import test_layer4_plan_refresh as pr
import test_layer4_race_week_brief as rb

from layer4.single_session import (
    SingleSessionRequest,
    llm_layer4_single_session_synthesize,
)
from layer4.plan_create import llm_layer4_plan_create
from layer4.plan_refresh import llm_layer4_plan_refresh
from layer4.race_week_brief import llm_layer4_race_week_brief

pytestmark = requires_anthropic_api_key


def _assert_common(payload, *, expected_pattern: str | None = None) -> None:
    """Shared structural checks across the four entry points."""
    assert payload.model_synthesizer == "claude-sonnet-4-6"
    assert payload.input_tokens_total > 0
    assert payload.output_tokens_total > 0
    assert payload.llm_call_count > 0
    assert payload.latency_ms_total > 0
    if expected_pattern is not None:
        assert payload.pattern == expected_pattern


class TestLayer4SmokeParity:
    """One real-LLM round-trip per Layer 4 entry point. Gated on the key."""

    def test_single_session_cardio(self):
        """Pattern B on-demand cardio synthesis (D-63) end-to-end."""
        req = SingleSessionRequest(
            sport="running", duration_min=60, intensity="easy", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            user_id=42,
            request=req,
            layer1_payload=ss._layer1(),
            layer2c_payload_for_locale=ss._layer2c(),
            layer2d_payload=ss._layer2d(),
            layer3a_payload=ss._layer3a(),
            suggestion_id=999,
            etl_version_set={"layer0": "v7"},
            session_date=date(2026, 6, 1),
        )
        _assert_common(payload, expected_pattern="B")
        assert payload.sessions, "single-session synthesis produced no session"
        assert len(payload.sessions) == 1

    def test_single_session_strength(self):
        """Pattern B on-demand strength synthesis — exercises the exercise
        pool / injury-accommodation path, not just cardio."""
        req = SingleSessionRequest(
            sport="strength", duration_min=45, intensity="moderate", locale_slug="home_gym"
        )
        payload = llm_layer4_single_session_synthesize(
            user_id=42,
            request=req,
            layer1_payload=ss._layer1(),
            layer2c_payload_for_locale=ss._layer2c(),
            layer2d_payload=ss._layer2d(),
            layer3a_payload=ss._layer3a(),
            suggestion_id=1000,
            etl_version_set={"layer0": "v7"},
            session_date=date(2026, 6, 1),
        )
        _assert_common(payload, expected_pattern="B")
        assert payload.sessions

    def test_plan_create_event_mode(self):
        """Pattern A multi-phase plan create (event-mode, full cone)."""
        payload = llm_layer4_plan_create(
            **pc._call_kwargs(),
            race_event_payload=pc._race_event(),
        )
        _assert_common(payload, expected_pattern="A")
        assert payload.phase_structure is not None
        assert payload.validator_results

    def test_plan_refresh_t1(self):
        """T1 plan refresh over a short scope window (Pattern B engine)."""
        payload = llm_layer4_plan_refresh(
            user_id=42,
            tier="T1",
            refresh_scope_start=pr._T1_START,
            refresh_scope_end=pr._T1_END,
            layer1_payload=pr._layer1(),
            layer2_bundle=pr._layer2_bundle(),
            layer3a_payload=pr._layer3a(),
            layer3b_payload=pr._layer3b(),
            prior_plan_session_window=pr._prior_window(pr._T1_START, pr._T1_END),
            parsed_intent=None,
            plan_version_id=2,
            plan_version_id_parent=1,
            etl_version_set={"layer0": "v7"},
        )
        _assert_common(payload)
        assert payload.sessions is not None

    def test_race_week_brief(self):
        """Race-week brief synthesis over the full cone + taper window."""
        payload = llm_layer4_race_week_brief(
            user_id=42,
            layer1_payload=rb._layer1(),
            layer2a_payload=rb._layer2a(),
            layer2b_payload=rb._layer2b(),
            layer2c_payloads={"home_gym": rb._layer2c()},
            layer2d_payload=rb._layer2d(),
            layer2e_payload=rb._layer2e(),
            layer3a_payload=rb._layer3a(),
            layer3b_payload=rb._layer3b(event_date=rb._EVENT_DATE),
            race_event_payload=rb._race_event_payload(),
            prior_plan_session_window=[rb._prior_taper_session()],
            plan_version_id=7,
            etl_version_set={"layer0": "v7"},
            today=rb._TODAY,
        )
        _assert_common(payload)
        assert payload.sessions is not None
