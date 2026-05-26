"""Guard the Anthropic request shape for the Layer 4 production callers.

The fake-based suites inject a stub LLM caller, so the real request
construction in each `_default_*_caller` was never exercised — which is
how a forced `tool_choice` + extended `thinking` combination (rejected by
the API with a 400) shipped to production undetected. These tests mock
the SDK client and assert the request the production callers actually
build.

The request shape now lives in one place — `llm_invocation.invoke_tool_call`
— which every Layer 4 caller delegates to (the same shared helper Layer 3A/3B
use). These tests therefore assert each caller *routes through* that helper
correctly: the relaxed shape under thinking, the forced shape with thinking
off, the SDK-error → `Layer4OutputError` mapping, and that the helper's
forced-tool retry (added for the 3A/3B reliability fix) is now distributed to
the Layer 4 callers too.

Invariant: extended thinking is incompatible with a forced `tool_choice`,
with `temperature != 1`, and with `max_tokens <= budget_tokens` (max_tokens
is the combined thinking + visible-output budget, so it must exceed the
thinking budget). When thinking is enabled the callers must relax
`tool_choice` to `auto`, `temperature` to `1.0`, and raise `max_tokens`
above `budget_tokens`; when it's off they keep the forced tool + the
requested temperature + the requested max_tokens. When a thinking attempt
returns no tool_use block the helper retries once with the forced tool.
SDK errors must surface as `Layer4OutputError`, not bubble as a 500.
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


class _NoToolMsg:
    content: list = []
    usage = _Usage()
    stop_reason = "end_turn"


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


def _fake_anthropic_sequence(recorder, msgs):
    """Returns successive `msgs` on successive `create` calls (records the
    LATEST call's kwargs + bumps `recorder['n']`). Drives the thinking-miss →
    forced-retry path through a Layer 4 caller."""
    state = {"i": 0}

    class _Messages:
        def create(self, **kwargs):
            recorder.clear()
            recorder.update(kwargs)
            i = state["i"]
            state["i"] += 1
            recorder["n"] = state["i"]
            return msgs[min(i, len(msgs) - 1)]

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
    # max_tokens is the combined thinking + output budget; it must exceed the
    # thinking budget or the API 400s. Output allowance (4000) preserved on top.
    assert rec["max_tokens"] == 9000
    assert rec["max_tokens"] > rec["thinking"]["budget_tokens"]


@pytest.mark.parametrize("caller", CALLERS)
def test_thinking_off_keeps_forced_tool(caller, monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 0)

    assert rec["tool_choice"] == {"type": "tool", "name": "emit"}
    assert rec["temperature"] == 0.2
    assert rec["max_tokens"] == 4000
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


@pytest.mark.parametrize("caller", CALLERS)
def test_thinking_miss_falls_back_to_forced(caller, monkeypatch):
    """The shared helper's forced-tool retry reaches the Layer 4 callers: a
    thinking attempt that returns no tool_use block triggers one forced
    (thinking-off) retry, whose result the caller returns."""
    rec: dict = {}
    monkeypatch.setattr(
        anthropic, "Anthropic", _fake_anthropic_sequence(rec, [_NoToolMsg(), _Msg()])
    )

    out = caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 5000)

    assert rec["n"] == 2  # thinking attempt + forced-tool retry
    assert out.tool_args == {"ok": True}
    # The recorded (final) request is the forced-tool fallback: no thinking.
    assert rec["tool_choice"] == {"type": "tool", "name": "emit"}
    assert "thinking" not in rec
