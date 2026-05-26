"""Guard the Anthropic request shape for the shared invocation + Layer 3 callers.

Layer 3A + Layer 3B fire their LLM calls FIRST in every plan-create /
plan-refresh / race-week-brief / single-session orchestration, before any
Layer 4 call. They carried the same extended-thinking incompatibility that
PR #170/#171 fixed in the Layer 4 callers (forced `tool_choice` + `temperature
!= 1` + `max_tokens <= budget_tokens` → API 400 → 500), so the fixed Layer 4
code was never reached. The fix routes all callers through the shared
`llm_invocation.invoke_tool_call`; these tests mock the SDK and assert both the
shared helper's request shape and that the Layer 3 wrappers map failures to
their typed OutputErrors instead of bubbling a raw 500.
"""

import anthropic
import pytest

# Load the layer4 consumer graph before importing layer3a/layer3b.builder
# directly. There is a pre-existing import cycle (layer3a.builder →
# layer4.context → layer4 → orchestrator → layer3a.cached_wrapper →
# layer3a.builder) that is masked in the full suite because another module
# imports layer4 first; importing it here keeps this file runnable in isolation.
import layer4  # noqa: F401
from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer3a.builder import Layer3AOutputError, _default_llm_caller as l3a_caller
from layer3b.builder import Layer3BOutputError, _default_llm_caller as l3b_caller

_TOOL = {
    "name": "emit",
    "description": "test tool",
    "input_schema": {"type": "object", "properties": {}},
}

# Layer-3 wrappers + their typed error class — the request shape lives in the
# shared helper, so both must build identical requests through it.
WRAPPERS = [
    (l3a_caller, Layer3AOutputError),
    (l3b_caller, Layer3BOutputError),
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


def _fake_anthropic(recorder, *, raise_exc=None, msg=None):
    class _Messages:
        def create(self, **kwargs):
            recorder.update(kwargs)
            if raise_exc is not None:
                raise raise_exc
            return msg if msg is not None else _Msg()

    class _Client:
        def __init__(self, *args, **kwargs):
            self.messages = _Messages()

    return _Client


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


# ─── Shared helper (llm_invocation.invoke_tool_call) ─────────────────────────


def test_helper_thinking_on_relaxes_all_three(monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    result = invoke_tool_call(
        system_prompt="sys",
        user_prompt="user",
        tool_schema=_TOOL,
        model="claude-sonnet-4-6",
        temperature=0.2,
        max_tokens=4000,
        extended_thinking_budget=5000,
    )

    assert rec["tool_choice"] == {"type": "auto"}
    assert rec["temperature"] == 1.0
    assert rec["thinking"] == {"type": "enabled", "budget_tokens": 5000}
    # max_tokens = output allowance + thinking budget; must exceed budget_tokens.
    assert rec["max_tokens"] == 9000
    assert rec["max_tokens"] > rec["thinking"]["budget_tokens"]
    assert result.tool_args == {"ok": True}
    assert (result.input_tokens, result.output_tokens) == (10, 20)


def test_helper_thinking_off_keeps_forced_tool(monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    invoke_tool_call(
        system_prompt="sys",
        user_prompt="user",
        tool_schema=_TOOL,
        model="claude-sonnet-4-6",
        temperature=0.2,
        max_tokens=4000,
        extended_thinking_budget=0,
    )

    assert rec["tool_choice"] == {"type": "tool", "name": "emit"}
    assert rec["temperature"] == 0.2
    assert rec["max_tokens"] == 4000
    assert "thinking" not in rec


def test_helper_api_error_becomes_thinking_tool_call_error(monkeypatch):
    class _Err(anthropic.APIError):
        def __init__(self):  # bypass SDK's request/body-requiring init
            pass

    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic({}, raise_exc=_Err()))

    with pytest.raises(ThinkingToolCallError) as exc_info:
        invoke_tool_call(
            system_prompt="sys",
            user_prompt="user",
            tool_schema=_TOOL,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=5000,
        )
    assert exc_info.value.code == "anthropic_api_error"


def test_helper_missing_tool_block_raises(monkeypatch):
    class _NoToolMsg:
        content = []
        usage = _Usage()

    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic({}, msg=_NoToolMsg()))

    with pytest.raises(ThinkingToolCallError) as exc_info:
        invoke_tool_call(
            system_prompt="sys",
            user_prompt="user",
            tool_schema=_TOOL,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=5000,
        )
    assert exc_info.value.code == "schema_violation"


def test_helper_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ThinkingToolCallError) as exc_info:
        invoke_tool_call(
            system_prompt="sys",
            user_prompt="user",
            tool_schema=_TOOL,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=5000,
        )
    assert exc_info.value.code == "anthropic_api_key_missing"


# ─── Layer 3A + 3B production wrappers (delegate to the shared helper) ────────


@pytest.mark.parametrize("caller, _err", WRAPPERS)
def test_layer3_wrapper_thinking_on_relaxes(caller, _err, monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 4000)

    assert rec["tool_choice"] == {"type": "auto"}
    assert rec["temperature"] == 1.0
    assert rec["max_tokens"] == 8000
    assert rec["max_tokens"] > rec["thinking"]["budget_tokens"]


@pytest.mark.parametrize("caller, _err", WRAPPERS)
def test_layer3_wrapper_thinking_off_keeps_forced_tool(caller, _err, monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(rec))

    caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.0, 2000, 0)

    assert rec["tool_choice"] == {"type": "tool", "name": "emit"}
    assert rec["temperature"] == 0.0
    assert rec["max_tokens"] == 2000
    assert "thinking" not in rec


@pytest.mark.parametrize("caller, err_cls", WRAPPERS)
def test_layer3_wrapper_api_error_becomes_typed_output_error(caller, err_cls, monkeypatch):
    class _Err(anthropic.APIError):
        def __init__(self):
            pass

    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic({}, raise_exc=_Err()))

    with pytest.raises(err_cls) as exc_info:
        caller("sys", "user", _TOOL, "claude-sonnet-4-6", 0.2, 4000, 4000)
    assert exc_info.value.code == "anthropic_api_error"
