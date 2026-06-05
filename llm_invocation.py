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
    # Construct with an explicit `timeout`. WITHOUT it the SDK auto-derives a
    # non-streaming timeout and REFUSES any call that could exceed 10 min:
    # `_calculate_nonstreaming_timeout` raises `ValueError("Streaming is
    # required ...")` once `(3600 * max_tokens) / 128000 > 600`, i.e. max_tokens
    # > 21,333. The guard runs only when the request timeout is unset AND the
    # client timeout is the SDK default, so a concrete client timeout disables it
    # for EVERY caller. The block-mode synthesizer ceiling (21,600) plus the
    # +thinking stack (21,600 + 5,000 = 26,600) clears that threshold, so the
    # guard fired as an UNTYPED ValueError that escaped the layer's typed-error
    # contract and surfaced as the route's generic "failed unexpectedly" (prod
    # pv=43/44 — the first run whose seam re-synth used the block ceiling; the
    # forced-retry path at 21,600 trips it too, so primary blocks were equally
    # exposed). The Vercel function caps at 300s, so a 10-min request is
    # impossible here and the guard is a pure false positive. Also pass `timeout`
    # per-request below, since an older SDK keys the guard off the per-request
    # arg rather than the client. Overridable via env for non-serverless use.
    request_timeout_s = float(os.environ.get("LLM_REQUEST_TIMEOUT_S", "600"))
    client = anthropic.Anthropic(api_key=api_key, timeout=request_timeout_s)
    tool_name = tool_schema["name"]

    # Diagnostics captured from the most recent _attempt that produced NO usable
    # tool_use block — so the terminal `schema_violation` can report what the
    # model actually emitted (how many output tokens, against which ceiling, and
    # — env-gated — a prefix of the raw text) rather than just `stop_reason`. A
    # forced retry pinned at `stop_reason=max_tokens` with a large output_tokens
    # count means genuine runaway/dense output; a small count means the model
    # stopped early for another reason. Without this the cause is unfalsifiable
    # from the logs (the failing attempt's usage was discarded).
    last_miss: dict[str, Any] = {}

    # Cumulative wall-clock latency across EVERY `_attempt` in this call,
    # including a failed thinking attempt that emitted no usable tool block.
    # The winning ToolCallResult reports this sum (not just its own attempt's
    # latency) so the caller's per-block budget guard sees the TRUE time the
    # block spent: a thinking runaway that burns ~430s then a ~110s forced
    # retry must count as ~540s, not 110s — otherwise the guard (which keys off
    # the returned latency) lets a doomed next attempt start and 504s the
    # whole function.
    latency_acc: dict[str, int] = {"ms": 0}

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
            # Per-request timeout too — see the client-construction note above.
            # The client timeout suppresses the installed SDK's guard; this also
            # covers an older SDK whose guard keys off the per-request arg.
            "timeout": request_timeout_s,
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
        latency_acc["ms"] += latency_ms

        stop_reason = getattr(msg, "stop_reason", None)
        out_tokens = getattr(getattr(msg, "usage", None), "output_tokens", None)
        ceiling = request_kwargs["max_tokens"]
        for block in msg.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and block.name == tool_name
            ):
                tool_args = dict(block.input)
                # A tool_use block with EMPTY args is a non-answer: under
                # extended thinking the model can spend its whole token budget
                # on the thinking block and emit a contentless tool call
                # (observed in prod for the Layer 4 synthesizer: output pinned
                # at the max_tokens+budget ceiling, `tool_args={}`). Treat it
                # like a missing block so the forced-tool retry below (thinking
                # off → the full output budget, and a forced tool_choice the
                # model cannot decline) fires — instead of the caller re-rolling
                # another expensive thinking attempt that truncates the same way.
                if not tool_args:
                    last_miss.update(
                        out_tokens=out_tokens, ceiling=ceiling,
                        thinking=thinking_budget, kind="empty_tool_args",
                    )
                    # #316 Slice 0 diagnostic — measure the per-attempt cost +
                    # outcome. The per-attempt `latency_ms` in this print is THIS
                    # call only; the returned ToolCallResult.latency_ms carries
                    # the cumulative `latency_acc` (this attempt + any prior
                    # failed one), so the caller's per-block budget guard sees
                    # true wall time rather than just the winning attempt's.
                    print(
                        f"invoke_tool_call: {tool_name} attempt "
                        f"(thinking={thinking_budget}) {latency_ms}ms "
                        f"outcome=empty_tool_args out_tokens={out_tokens}/"
                        f"{ceiling} stop_reason={stop_reason}"
                    )
                    return None, stop_reason
                print(
                    f"invoke_tool_call: {tool_name} attempt "
                    f"(thinking={thinking_budget}) {latency_ms}ms "
                    f"outcome=tool_use_ok out_tokens={out_tokens}/{ceiling} "
                    f"stop_reason={stop_reason}"
                )
                return (
                    ToolCallResult(
                        tool_args=tool_args,
                        input_tokens=msg.usage.input_tokens,
                        output_tokens=msg.usage.output_tokens,
                        latency_ms=latency_acc["ms"],
                    ),
                    stop_reason,
                )
        # No matching tool_use block at all. Capture usage + (env-gated) a prefix
        # of any text/partial content the model emitted instead, so the terminal
        # error can distinguish runaway output (large out_tokens at the ceiling)
        # from an early stop, and show what it produced in place of the call.
        miss: dict[str, Any] = dict(
            out_tokens=out_tokens, ceiling=ceiling,
            thinking=thinking_budget, kind="no_tool_use_block",
        )
        if os.environ.get("PLAN_GEN_LOG_FAILED_ATTEMPT") == "1":
            text_prefix = "".join(
                getattr(b, "text", "") for b in msg.content
                if getattr(b, "type", None) == "text"
            )[:600]
            if text_prefix:
                miss["text_prefix"] = text_prefix
        last_miss.update(miss)
        # #316 Slice 0 diagnostic — see the empty_tool_args branch above.
        print(
            f"invoke_tool_call: {tool_name} attempt "
            f"(thinking={thinking_budget}) {latency_ms}ms "
            f"outcome=no_tool_use_block out_tokens={out_tokens}/{ceiling} "
            f"stop_reason={stop_reason}"
        )
        return None, stop_reason

    result, stop_reason = _attempt(extended_thinking_budget)
    if result is not None:
        return result

    # No usable tool_use block (absent, or present-but-empty). Under extended
    # thinking the tool is merely offered (`auto`), so the model can skip it OR
    # exhaust its token budget thinking and emit a contentless tool call — both
    # recurring failure modes. Retry once with thinking off + the forced tool,
    # which cannot be declined and gets the full output budget.
    if extended_thinking_budget > 0:
        print(
            f"invoke_tool_call: {tool_name} returned no usable tool_use block on "
            f"the thinking attempt (stop_reason={stop_reason}; absent or empty); "
            f"retrying with thinking off + forced tool_choice"
        )
        result, stop_reason = _attempt(0)
        if result is not None:
            return result

    # The forced retry (thinking off) is the reliable floor: its `max_tokens` is
    # the entire output budget. `last_miss` reports what that attempt actually
    # produced so a `stop_reason=max_tokens` failure is diagnosable — a large
    # out_tokens at the ceiling is genuine runaway/dense output (no ceiling bump
    # cures it); a small one stopped early for another reason.
    miss_detail = ""
    if last_miss:
        miss_detail = (
            f"; last_attempt_output_tokens={last_miss.get('out_tokens')}"
            f"/ceiling={last_miss.get('ceiling')}"
            f" thinking={last_miss.get('thinking')} kind={last_miss.get('kind')}"
        )
        if last_miss.get("text_prefix"):
            miss_detail += f" text_prefix={last_miss['text_prefix']!r}"
    raise ThinkingToolCallError(
        "schema_violation",
        detail=(
            f"model did not emit a {tool_name} tool_use block "
            f"(stop_reason={stop_reason}){miss_detail}"
        ),
    )


__all__ = ["ToolCallResult", "ThinkingToolCallError", "invoke_tool_call"]
