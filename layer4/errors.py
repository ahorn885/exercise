"""Layer 4 typed exception classes per `Layer4_Spec.md` §3.5.

`Layer4InputError` raises on §4 precondition failures (caller is expected to
pre-validate; Layer 4 raises defensively if a check is missed).
`Layer4OutputError` raises on terminal output failures the synthesizer could
not produce within the retry cap (rare; §5.5 best-effort fallback usually
absorbs).
"""

from __future__ import annotations


class Layer4Error(Exception):
    """Base class for Layer 4 typed errors. Each subclass carries a stable
    `code` string the orchestrator routes on per `Layer4_Spec.md` §3.5."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class Layer4InputError(Layer4Error):
    """Precondition failure per `Layer4_Spec.md` §4. Fail-fast — first failing
    rule raises; no error accumulation across rules. Caller routes per code."""


class Layer4OutputError(Layer4Error):
    """Synthesizer could not produce an accepted plan within retry cap AND the
    best-effort fallback could not be assembled. Rare in v1."""
