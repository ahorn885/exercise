"""Regression: the synthesizer must pin an explicit request timeout so the
Anthropic SDK's non-streaming 10-minute guard never fires.

Prod pv=43/44 crashed with an UNTYPED ValueError that escaped the layer's
typed-error contract and surfaced as the route catch-all "Plan generation
failed unexpectedly":

    ValueError: Streaming is required for operations that may take longer
    than 10 minutes.

The SDK raises this when `(3600 * max_tokens) / 128000 > 600` (max_tokens >
21,333) UNLESS a concrete timeout is set. The block-mode synthesizer ceiling
(21,600) plus the +thinking stack (21,600 + 5,000 = 26,600) clears that
threshold, so every synthesis request must pin a timeout — on the client
(installed SDK keys the guard off the client timeout) AND per-request (older
SDK keys it off the per-request arg).
"""

from __future__ import annotations

import sys
from typing import Any

import llm_invocation


class _Usage:
    input_tokens = 100
    output_tokens = 50


class _ToolUse:
    type = "tool_use"
    name = "record_phase_sessions"
    input = {"sessions": []}


class _Msg:
    content = [_ToolUse()]
    stop_reason = "tool_use"
    usage = _Usage()


def _install_capturing_anthropic(monkeypatch):
    """Install a fake `anthropic` module that records the client + request
    kwargs, so the timeout can be asserted without a network call."""
    client_kw: dict[str, Any] = {}
    request_kw: dict[str, Any] = {}

    class _Messages:
        def create(self, **kw: Any) -> _Msg:
            request_kw.clear()
            request_kw.update(kw)
            return _Msg()

    class _Client:
        def __init__(self, **kw: Any) -> None:
            client_kw.clear()
            client_kw.update(kw)
            self.messages = _Messages()

    class _FakeAnthropic:
        Anthropic = _Client

        class APIError(Exception):
            ...

    monkeypatch.setitem(sys.modules, "anthropic", _FakeAnthropic)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT_S", raising=False)
    return client_kw, request_kw


def test_thinking_attempt_pins_timeout_on_client_and_request(monkeypatch):
    client_kw, request_kw = _install_capturing_anthropic(monkeypatch)
    llm_invocation.invoke_tool_call(
        system_prompt="s", user_prompt="u",
        tool_schema={"name": "record_phase_sessions", "type": "object"},
        model="claude-sonnet-4-6", temperature=1.0,
        max_tokens=21600, extended_thinking_budget=5000,
    )
    assert client_kw["timeout"] == 600.0
    assert request_kw["timeout"] == 600.0
    # The thinking attempt stacks budget onto max_tokens — this is exactly the
    # 26,600 that crossed the SDK guard threshold in prod.
    assert request_kw["max_tokens"] == 26600


def test_forced_retry_attempt_pins_timeout(monkeypatch):
    # extended_thinking_budget=0 takes the forced-tool path directly; assert it
    # pins the timeout too (21,600 alone also clears the 21,333 threshold).
    client_kw, request_kw = _install_capturing_anthropic(monkeypatch)
    llm_invocation.invoke_tool_call(
        system_prompt="s", user_prompt="u",
        tool_schema={"name": "record_phase_sessions", "type": "object"},
        model="claude-sonnet-4-6", temperature=0.2,
        max_tokens=21600, extended_thinking_budget=0,
    )
    assert client_kw["timeout"] == 600.0
    assert request_kw["timeout"] == 600.0


def test_env_override_timeout(monkeypatch):
    client_kw, request_kw = _install_capturing_anthropic(monkeypatch)
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_S", "123")
    llm_invocation.invoke_tool_call(
        system_prompt="s", user_prompt="u",
        tool_schema={"name": "record_phase_sessions", "type": "object"},
        model="claude-sonnet-4-6", temperature=0.2,
        max_tokens=4000, extended_thinking_budget=0,
    )
    assert client_kw["timeout"] == 123.0
    assert request_kw["timeout"] == 123.0


def test_client_built_with_non_default_timeout():
    """The fix depends on the SDK skipping its non-streaming guard when the
    client carries a concrete (non-default) timeout — the guard's call site is
    gated on `self._client.timeout == DEFAULT_TIMEOUT`. Assert that constructing
    the client the way `invoke_tool_call` does yields a non-default timeout, so
    the guard is bypassed. (Kept independent of the SDK's private guard method,
    whose signature varies across versions.)"""
    from anthropic import Anthropic

    pinned = Anthropic(api_key="x", timeout=600.0)
    default = Anthropic(api_key="x")
    assert pinned.timeout != default.timeout
    assert pinned.timeout == 600.0
