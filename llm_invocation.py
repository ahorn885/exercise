"""Shared Anthropic extended-thinking tool-call invocation — single site.

Every layer that calls the Anthropic API for a forced tool-use result (Layer
3A, Layer 3B, and the five Layer 4 callers) builds the same request shape.
Extended thinking constrains that shape three ways, and getting any one wrong
yields an API 400 that surfaces to the athlete as a 500:

  1. `tool_choice` must be `auto` (not a forced `{"type": "tool", ...}`).
  2. `temperature` must be 1.
  3. `max_tokens` must EXCEED `budget_tokens` — `max_tokens` is the combined
     thinking + visible-output budget, so the thinking budget is stacked on
     top of the intended output allowance.

That request shape was duplicated per-caller, which is how two of the three
incompatibilities shipped to production undetected (each fix had to be copied
into every caller). This module is the one authoritative construction; callers
delegate here and map `ThinkingToolCallError` onto their own typed errors.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCallResult:
    """Raw result of one tool-call invocation, before payload assembly."""

    tool_args: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ThinkingToolCallError(Exception):
    """Raised on a failed tool-call invocation. Carries a stable `code`
    (`anthropic_api_key_missing` / `anthropic_api_error` / `schema_violation`)
    + optional detail. Each layer caller maps this to its own typed
    OutputError so the existing per-layer error contracts are preserved."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def invoke_tool_call(
    *,
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> ToolCallResult:
    """Invoke the Anthropic SDK for a single forced tool-use result.

    With `extended_thinking_budget == 0` the request keeps a FORCED
    `tool_choice` + the passed `temperature` + the passed `max_tokens` —
    which guarantees a tool_use block. With a positive budget it relaxes all
    three per the module invariant (a forced `tool_choice` is incompatible
    with extended thinking), which means the model MAY decline to call the
    tool and "think out loud" instead, leaving no tool_use block.

    When the thinking attempt comes back without the tool block, retry ONCE
    with thinking off + the forced tool — which the model cannot decline —
    trading the (already-unproductive) thinking step for a guaranteed result.
    `stop_reason` is logged on the miss so the cause is never opaque.

    Raises `ThinkingToolCallError` on a missing API key, any
    `anthropic.APIError`, or a response still missing the tool_use block after
    the forced-tool retry.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ThinkingToolCallError(
            "anthropic_api_key_missing",
            detail="ANTHROPIC_API_KEY environment variable is not set",
        )
    client = anthropic.Anthropic(api_key=api_key)
    tool_name = tool_schema["name"]

    def _attempt(thinking_budget: int) -> tuple[ToolCallResult | None, str | None]:
        """One `messages.create` call. Returns `(result, stop_reason)`;
        `result` is None when the response carried no matching tool_use
        block. Raises `ThinkingToolCallError` on an `anthropic.APIError`."""
        request_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": [tool_schema],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if thinking_budget > 0:
            # Extended thinking constrains the request: tool_choice must be
            # `auto` (not forced), temperature must be 1, and max_tokens must
            # exceed budget_tokens (max_tokens is the combined thinking +
            # visible-output budget). Stacking the budget on top of the output
            # allowance preserves the output room; the tool is still offered
            # via `tools` and required by the prompt body.
            request_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            request_kwargs["tool_choice"] = {"type": "auto"}
            request_kwargs["temperature"] = 1.0
            request_kwargs["max_tokens"] = max_tokens + thinking_budget

        start = time.monotonic()
        try:
            msg = client.messages.create(**request_kwargs)
        except anthropic.APIError as exc:
            raise ThinkingToolCallError(
                "anthropic_api_error",
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc
        latency_ms = int((time.monotonic() - start) * 1000)

        stop_reason = getattr(msg, "stop_reason", None)
        for block in msg.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and block.name == tool_name
            ):
                return (
                    ToolCallResult(
                        tool_args=dict(block.input),
                        input_tokens=msg.usage.input_tokens,
                        output_tokens=msg.usage.output_tokens,
                        latency_ms=latency_ms,
                    ),
                    stop_reason,
                )
        return None, stop_reason

    result, stop_reason = _attempt(extended_thinking_budget)
    if result is not None:
        return result

    # No tool_use block. Under extended thinking the tool is merely offered
    # (`auto`), so the model can legally skip it — the recurring failure mode.
    # Retry once with thinking off + the forced tool, which cannot be declined.
    if extended_thinking_budget > 0:
        print(
            f"invoke_tool_call: {tool_name} returned no tool_use block on the "
            f"thinking attempt (stop_reason={stop_reason}); retrying with "
            f"thinking off + forced tool_choice"
        )
        result, stop_reason = _attempt(0)
        if result is not None:
            return result

    raise ThinkingToolCallError(
        "schema_violation",
        detail=(
            f"model did not emit a {tool_name} tool_use block "
            f"(stop_reason={stop_reason})"
        ),
    )


__all__ = ["ToolCallResult", "ThinkingToolCallError", "invoke_tool_call"]
