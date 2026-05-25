"""Guard the Anthropic request shape for the Layer 4 production callers.

The fake-based suites inject a stub LLM caller, so the real request
construction in each `_default_*_caller` was never exercised — which is
how a forced `tool_choice` + extended `thinking` combination (rejected by
the API with a 400) shipped to production undetected. These tests mock
the SDK client and assert the request the production callers actually
build.

Invariant: extended thinking is incompatible with a forced `tool_choice`
and with `temperature != 1`. When thinking is enabled the callers must
relax `tool_choice` to `auto` and `temperature` to `1.0`; when it's off
they keep the forced tool + the requested temperature. SDK errors must
surface as `Layer4OutputError`, not bubble as a 500.
"""

import anthropic
import pytest

from layer4 import (
    per_phase,
    plan_refresh,
    race_week_brief,
    seam_review,
    single_session,
)
from layer4.errors import Layer4OutputError

_TOOL = {
    "name": "emit",
    "description": "test tool",
    "input_schema": {"type": "object", "properties": {}},
}

CALLERS = [
    per_phase._default_llm_caller,
    seam_review._default_seam_reviewer_caller,
    single_session._default_llm_caller,
    plan_refresh._default_llm_caller,
    race_week_brief._default_llm_caller,
]


class _Block:
    type = "tool_use"
    name = "emit"
    input = {"ok": True}


class _Usage:
    input_tokens = 10
    output_tokens = 20


class _Msg:
    content = [_Block()]
    usage = _Usage()


def _fake_anthropic(recorder, *, raise_exc=None):
    class _Messages:
        def create(self, **kwargs):
            recorder.update(kwargs)
            if raise_exc is not None:
                raise raise_exc
            return _Msg()

    class _Client:
        def __init__(self, *args, **kwargs):
            self.messages = _Messages()

    return _Client


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.mark.parametrize("caller", CALLERS)
def test_thinking_on_relaxes_tool_choice_and_temperature(caller, monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 5000)

    assert rec["tool_choice"] == {"type": "auto"}
    assert rec["temperature"] == 1.0
    assert rec["thinking"]["type"] == "enabled"
    assert rec["thinking"]["budget_tokens"] == 5000


@pytest.mark.parametrize("caller", CALLERS)
def test_thinking_off_keeps_forced_tool(caller, monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 0)

    assert rec["tool_choice"] == {"type": "tool", "name": "emit"}
    assert rec["temperature"] == 0.2
    assert "thinking" not in rec


@pytest.mark.parametrize("caller", CALLERS)
def test_anthropic_error_becomes_output_error(caller, monkeypatch):
    class _Err(anthropic.APIError):
        def __init__(self):  # bypass SDK's request/body-requiring init
            pass

    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec, raise_exc=_Err()))

    with pytest.raises(Layer4OutputError):
        caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 5000)
