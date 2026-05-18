"""Layer 4 orchestrator-side call telemetry per `Layer4_Spec.md` §9.6 + §14.3.5.

Distinct from `layer4/cache.py:CacheMetrics`, which observes the cache layer.
This module observes the Layer 4 *calls themselves* — verdict distribution
on Pattern A seam reviews, retry rates, cap-hit rates, cost/call estimates,
latency percentiles. The orchestrator's dashboards consume both:

- `CacheMetrics` answers "how often did we skip Layer 4 entirely?"
- `TelemetryAggregator` answers "for the calls we did make, what was the
  shape of those calls?"

§9.6 anchor: "Layer 4 itself emits NO cache metrics — Layer 4 only runs on
miss, so it cannot observe hits." The Layer 4 driver populates `CallMetrics`
from the synthesized `Layer4Payload` after each non-cache-hit call, and
the orchestrator hands it to the aggregator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from layer4.payload import Layer4Payload


# ─── Model pricing per Layer4_Spec.md §11.3 ───────────────────────────────


MODEL_PRICING_USD_PER_M: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-7": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
"""USD-per-million-token rates per Anthropic public list pricing.

Used by `CallMetrics.from_layer4_payload()` for the `cost_usd_estimate`
field. Callers pass `model_pricing=` to override (e.g., for batch-API
discount runs or for newer models not yet in this table). Unknown models
estimate at zero rather than raise — telemetry should degrade gracefully.
"""


# ─── Per-call snapshot ────────────────────────────────────────────────────


@dataclass(frozen=True)
class CallMetrics:
    """One Layer 4 call's observable shape.

    Constructed via `from_layer4_payload()` after the call returns; immutable
    once constructed. The aggregator stores these and exposes rollups across
    calls per entry point.

    `pattern == 'A'`-specific fields (`seam_verdict_histogram`,
    `seam_unresolved_count`) are empty / zero on Pattern B calls.
    """

    entry_point: str
    """One of 'plan_create' | 'plan_refresh' | 'single_session_synthesize'
    | 'race_week_brief'."""

    pattern: Literal["A", "B"]

    model_synthesizer: str
    model_seam_reviewer: str | None

    retries_used_total: int
    """Sum of `synthesis_metadata.retries_used` across all phases (Pattern A);
    inferred from `len(validator_results) - 1` on Pattern B (each pass is a
    retry; final accepted may be synthesized on cap-hit, see `cap_hit`)."""

    cap_hit: bool
    """True iff any `best_effort_plan` observation was emitted (per-phase
    cap-hit OR cross-phase blocker demotion per §5.5)."""

    seam_verdict_histogram: dict[str, int]
    """Per-verdict count across all SeamReview rows. Empty on Pattern B."""

    seam_unresolved_count: int
    """Count of `seam_unresolved` observations emitted. Per §6.2 per-seam cap
    + retry-budget exhaustion."""

    validator_pass_count: int
    rule_failure_count: int
    blocker_failure_count: int

    input_tokens: int
    output_tokens: int
    llm_call_count: int
    latency_ms_total: int

    cost_usd_estimate: float
    """`input_tokens * input_price + output_tokens * output_price`, both
    rate-adjusted to per-token. v1 uses `model_synthesizer` price for ALL
    tokens — seam-reviewer tokens are a small fraction in practice; a
    per-call-split would require Layer4Payload to expose synth-vs-seam
    token breakdown (deferred to v2)."""

    best_effort_emitted: bool
    intensity_modulated_session_count: int

    @classmethod
    def from_layer4_payload(
        cls,
        payload: Layer4Payload,
        *,
        entry_point: str,
        model_pricing: dict[str, dict[str, float]] | None = None,
    ) -> "CallMetrics":
        """Project a Layer4Payload + entry_point label into a CallMetrics.

        `entry_point` is supplied separately because Layer4Payload.mode
        collapses 'plan_create' / 'plan_refresh' / 'single_session_synthesize'
        / 'race_week_brief' onto its own enum — same names but the caller
        knows which entry point fired (T3 cross-phase refresh emits mode
        'plan_refresh' even when it routed through plan_create's Pattern A
        engine, so the orchestrator's entry-point label is canonical).

        `model_pricing` defaults to `MODEL_PRICING_USD_PER_M`; pass an
        overlay dict to handle batch-API discounts or newer models.
        """
        pricing = model_pricing if model_pricing is not None else MODEL_PRICING_USD_PER_M

        seam_verdict_histogram: dict[str, int] = {}
        if payload.seam_reviews:
            for sr in payload.seam_reviews:
                seam_verdict_histogram[sr.reviewer_verdict] = (
                    seam_verdict_histogram.get(sr.reviewer_verdict, 0) + 1
                )

        best_effort_emitted = any(
            o.category == "best_effort_plan" for o in payload.notable_observations
        )

        retries_used_total = 0
        if payload.pattern == "A" and payload.phase_structure is not None:
            retries_used_total = sum(
                p.synthesis_metadata.retries_used for p in payload.phase_structure.phases
            )
        else:
            # Pattern B: validator pass count - 1 (last pass is accepted; each
            # prior pass was a retry). On cap-hit, the LAST entry is a
            # synthesized accepted pass on top of the real failing one —
            # back that out when the cap-hit signal is present AND the
            # last pass carries the cap-hit shape (accepted + non-empty
            # rule_failures all demoted to 'warning').
            n = len(payload.validator_results)
            if n > 0:
                retries_used_total = max(0, n - 1)
                if best_effort_emitted and n >= 2:
                    last = payload.validator_results[-1]
                    if (
                        last.accepted
                        and last.rule_failures
                        and all(rf.severity == "warning" for rf in last.rule_failures)
                    ):
                        retries_used_total = max(0, retries_used_total - 1)
        seam_unresolved_count = sum(
            1 for o in payload.notable_observations if o.category == "seam_unresolved"
        )

        rule_failure_count = 0
        blocker_failure_count = 0
        for vr in payload.validator_results:
            rule_failure_count += len(vr.rule_failures)
            blocker_failure_count += sum(
                1 for rf in vr.rule_failures if rf.severity == "blocker"
            )

        intensity_modulated_session_count = sum(
            1 for s in payload.sessions if "intensity_modulated" in s.coaching_flags
        )

        rates = pricing.get(payload.model_synthesizer)
        if rates is None:
            cost_usd_estimate = 0.0
        else:
            cost_usd_estimate = (
                payload.input_tokens_total * rates["input"] / 1_000_000.0
                + payload.output_tokens_total * rates["output"] / 1_000_000.0
            )

        return cls(
            entry_point=entry_point,
            pattern=payload.pattern,
            model_synthesizer=payload.model_synthesizer,
            model_seam_reviewer=payload.model_seam_reviewer,
            retries_used_total=retries_used_total,
            cap_hit=best_effort_emitted,
            seam_verdict_histogram=seam_verdict_histogram,
            seam_unresolved_count=seam_unresolved_count,
            validator_pass_count=len(payload.validator_results),
            rule_failure_count=rule_failure_count,
            blocker_failure_count=blocker_failure_count,
            input_tokens=payload.input_tokens_total,
            output_tokens=payload.output_tokens_total,
            llm_call_count=payload.llm_call_count,
            latency_ms_total=payload.latency_ms_total,
            cost_usd_estimate=cost_usd_estimate,
            best_effort_emitted=best_effort_emitted,
            intensity_modulated_session_count=intensity_modulated_session_count,
        )


# ─── Rolling aggregator ────────────────────────────────────────────────────


@dataclass
class TelemetryAggregator:
    """Running aggregator across calls. Mutable; thread-safe is the caller's
    responsibility (orchestrator handles concurrency at a higher level).

    All getters accept an optional `entry_point` filter — None returns
    the rollup across every recorded call.
    """

    _calls: list[CallMetrics] = field(default_factory=list)

    def record(self, metrics: CallMetrics) -> None:
        self._calls.append(metrics)

    def _filter(self, entry_point: str | None) -> list[CallMetrics]:
        if entry_point is None:
            return list(self._calls)
        return [c for c in self._calls if c.entry_point == entry_point]

    def call_count(self, entry_point: str | None = None) -> int:
        return len(self._filter(entry_point))

    def total_cost_usd(self, entry_point: str | None = None) -> float:
        return sum(c.cost_usd_estimate for c in self._filter(entry_point))

    def average_cost_usd(self, entry_point: str | None = None) -> float:
        rows = self._filter(entry_point)
        if not rows:
            return 0.0
        return sum(c.cost_usd_estimate for c in rows) / len(rows)

    def cap_hit_rate(self, entry_point: str | None = None) -> float:
        rows = self._filter(entry_point)
        if not rows:
            return 0.0
        return sum(1 for c in rows if c.cap_hit) / len(rows)

    def average_retries(self, entry_point: str | None = None) -> float:
        rows = self._filter(entry_point)
        if not rows:
            return 0.0
        return sum(c.retries_used_total for c in rows) / len(rows)

    def latency_percentile_ms(
        self, percentile: float, entry_point: str | None = None
    ) -> int:
        """Returns the p{percentile} latency_ms_total across matching calls.

        `percentile` is in [0, 100]. Uses nearest-rank (linear-interpolation
        skipped for v1 — small N makes the distinction irrelevant).
        """
        if percentile < 0.0 or percentile > 100.0:
            raise ValueError("percentile must be in [0, 100]")
        rows = self._filter(entry_point)
        if not rows:
            return 0
        latencies = sorted(c.latency_ms_total for c in rows)
        if percentile == 0.0:
            return latencies[0]
        # Nearest-rank: rank = ceil(p/100 * N), 1-indexed.
        import math

        rank = max(1, math.ceil(percentile / 100.0 * len(latencies)))
        return latencies[min(rank - 1, len(latencies) - 1)]

    def aggregated_seam_verdict_histogram(
        self, entry_point: str | None = None
    ) -> dict[str, int]:
        """Sum of per-call seam_verdict_histograms. Always empty for Pattern B
        entry points."""
        agg: dict[str, int] = {}
        for c in self._filter(entry_point):
            for verdict, count in c.seam_verdict_histogram.items():
                agg[verdict] = agg.get(verdict, 0) + count
        return agg

    def seam_unresolved_count(self, entry_point: str | None = None) -> int:
        return sum(c.seam_unresolved_count for c in self._filter(entry_point))

    def intensity_modulated_session_count(
        self, entry_point: str | None = None
    ) -> int:
        return sum(
            c.intensity_modulated_session_count for c in self._filter(entry_point)
        )

    def summary(self, entry_point: str | None = None) -> dict[str, Any]:
        """Return a serializable rollup dict the orchestrator can ship to a
        dashboard or log line. All percentile values + averages computed lazily."""
        return {
            "entry_point": entry_point,
            "call_count": self.call_count(entry_point),
            "total_cost_usd": round(self.total_cost_usd(entry_point), 4),
            "average_cost_usd": round(self.average_cost_usd(entry_point), 4),
            "cap_hit_rate": round(self.cap_hit_rate(entry_point), 4),
            "average_retries": round(self.average_retries(entry_point), 3),
            "p50_latency_ms": self.latency_percentile_ms(50.0, entry_point),
            "p95_latency_ms": self.latency_percentile_ms(95.0, entry_point),
            "seam_verdict_histogram": self.aggregated_seam_verdict_histogram(
                entry_point
            ),
            "seam_unresolved_count": self.seam_unresolved_count(entry_point),
            "intensity_modulated_session_count": (
                self.intensity_modulated_session_count(entry_point)
            ),
        }


__all__ = [
    "CallMetrics",
    "MODEL_PRICING_USD_PER_M",
    "TelemetryAggregator",
]
