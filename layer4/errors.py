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


class Layer4ShapeInfeasibleError(Layer4Error):
    """Defensive backstop (§10.2) for the one surviving #214 blocker: synthesis
    was reached on a shape the 3D HITL gate should have parked — injury (2D)
    exclusions emptied a phase's strength pool below the workable floor.

    Detection authority is the 3D gate (`Layer3D_Spec.md` §5.2,
    `injury_pool_empty`), which parks the plan at `needs_review` before Layer 4
    runs; this fires only if that pre-check was bypassed (mirrors the §4
    "caller pre-checks; Layer 4 raises defensively" pattern). `code` carries the
    stable routing class (`cumulative_load_injury_infeasible`); `evidence` carries
    the phase, the post-exclusion usable-exercise count, and the triggering 2D
    exclusion ids. When raised, no sessions are written; the `plan_versions` row
    is rolled back per D-64 §6.2 atomic-write semantics."""

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        evidence: dict | None = None,
    ) -> None:
        self.evidence = evidence or {}
        super().__init__(code, detail)
