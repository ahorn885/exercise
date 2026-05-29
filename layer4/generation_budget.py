"""D-77 per-invocation wall-clock budget for resumable plan generation.

Layer 4 plan generation is resumable: each cron/poller pass replays the
already-cached week-blocks (fast cache HITs) and synthesizes the next few. A
single block's extended-thinking synthesis runs ~150s and the Vercel function
duration is capped (300s today, up to 800s on Pro). Without a budget the engine
greedily starts another block after the cap is effectively spent, the function
504s mid-synthesis, and that in-flight block's (billed) Anthropic call is wasted
-- every pass. This module lets the route set a per-invocation deadline; the
Pattern-A engine stops *starting new syntheses* once it is hit, returns the
blocks cached so far, and the next pass resumes from the cache.

The stop signal `Layer4GenerationIncomplete` is deliberately a **BaseException**
subclass: it is control flow, not an error, and must NOT be swallowed by the
broad `except Exception` handlers in the cached wrappers / orchestrator / route.
Only the route's explicit `except Layer4GenerationIncomplete` handles it (-> keep
the row 'generating', no failure). The deadline lives in a ContextVar so it needs
no plumbing through the orchestrator/cache-key surface, and defaults to unset --
when unset, `generation_deadline_passed()` is always False, so the engine's
behavior (and every existing test) is unchanged.
"""
from __future__ import annotations

import contextlib
import time
from contextvars import ContextVar

__all__ = [
    "Layer4GenerationIncomplete",
    "generation_deadline",
    "generation_deadline_passed",
]


class Layer4GenerationIncomplete(BaseException):
    """Raised by the Pattern-A engine when the per-invocation wall-clock budget
    is spent with blocks still to synthesize. NOT a failure: the blocks cached so
    far persist (per-block cache commits independently), so the caller keeps the
    plan 'generating' and the next resumable pass continues from the cache.
    BaseException so broad `except Exception` handlers in the synthesis path can't
    swallow this control-flow signal."""

    def __init__(self, blocks_cached: int):
        self.blocks_cached = blocks_cached
        super().__init__(
            f"generation budget spent after {blocks_cached} cached block(s); "
            "resuming next pass"
        )


_deadline_monotonic: ContextVar[float | None] = ContextVar(
    "plan_gen_deadline_monotonic", default=None
)


@contextlib.contextmanager
def generation_deadline(budget_s: float | None):
    """Set a per-invocation monotonic deadline `budget_s` seconds from now for
    the duration of the block. `budget_s` None/<=0 -> no deadline (engine runs to
    completion or the function cap, i.e. the pre-budget behavior)."""
    if budget_s is None or budget_s <= 0:
        token = _deadline_monotonic.set(None)
    else:
        token = _deadline_monotonic.set(time.monotonic() + budget_s)
    try:
        yield
    finally:
        _deadline_monotonic.reset(token)


def generation_deadline_passed() -> bool:
    """True once the per-invocation budget set by `generation_deadline` is spent.
    Always False when no deadline is set (default), so callers that do not opt in
    see no behavior change."""
    deadline = _deadline_monotonic.get()
    return deadline is not None and time.monotonic() >= deadline
