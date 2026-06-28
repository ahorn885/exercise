"""Recovery-aware planning guidance (#196 Phase 4, Slice 1).

Renders LLM-soft recovery guidance into the Layer-4 plan-refresh prompts from the
*already-hashed* ``Layer3APayload`` digest (channel (a), Andy 2026-06-28) — so no
new input is folded into the Layer-4 cache key (``layer3a_hash`` already carries
the whole 3A payload; ``recovery_guidance`` only surfaces fields it already holds).

Freshness-gated (Andy 2026-06-28): the strong-lean de-load guidance is injected
only when recent HRV/sleep data exists; otherwise an explicit "do not infer" line
keeps the LLM from hallucinating a recovery state from absent data. The mechanism
is LLM-soft — the prompt is informed, the LLM decides; this is not a deterministic
load-cut.

Single home so the wording is shared across the refresh tiers (and PerPhase /
RaceWeekBrief in later slices) rather than copy-pasted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from layer4.context import Layer3APayload

# Only the actionable 3A observation categories surface as recovery flags; the
# `opportunity` / `data_hygiene` categories are not recovery-relevant here.
_RECOVERY_FLAG_CATEGORIES = ("warning", "data_gap")


def format_recovery_guidance(layer3a_payload: "Layer3APayload") -> list[str]:
    """Build the recovery-state prompt block from the 3A digest.

    Returns Block A (the strong-lean recovery guidance, with the surfaced
    trajectory reasoning / per-discipline ACWR / recovery flags) when recent
    HRV or sleep data is present, else Block B (the explicit "do not infer"
    line). Output is prompt text only — it is not part of any cache key.
    """
    dd = layer3a_payload.data_density
    fresh = dd.recent_hrv_count > 0 or dd.recent_sleep_count > 0
    rt = layer3a_payload.recent_trajectory

    # Rule #15 — make the inject/skip decision diagnosable from /admin/logs.
    combined_zone = rt.acwr_status.combined.zone if rt.acwr_status.combined else None
    print(
        f"[recovery-guidance] fresh={fresh} short={rt.short_term.direction} "
        f"acwr_combined_zone={combined_zone} hrv_n={dd.recent_hrv_count} "
        f"sleep_n={dd.recent_sleep_count} injected_block={'A' if fresh else 'B'}"
    )

    if not fresh:
        return [
            "=== Recovery state (3A wellness) ===",
            "No recent HRV or sleep data in the integration window. Do not infer a "
            "recovery state or fatigue level from its absence — plan the normal "
            "progression for this phase.",
        ]

    lines = [
        "=== Recovery state (3A wellness — act on this) ===",
        f"Short-term trajectory: {rt.short_term.direction} — "
        f"{rt.short_term.reasoning_text}",
        f"Medium-term trajectory: {rt.medium_term.direction} — "
        f"{rt.medium_term.reasoning_text}",
    ]

    per_discipline = rt.acwr_status.per_discipline
    if per_discipline:
        lines.append("ACWR by discipline:")
        for discipline in sorted(per_discipline):
            entry = per_discipline[discipline]
            lines.append(
                f"  {discipline}: zone={entry.zone}, ratio={entry.ratio:.2f}"
            )

    flags = [
        o
        for o in layer3a_payload.notable_observations
        if o.category in _RECOVERY_FLAG_CATEGORIES
    ]
    if flags:
        lines.append("Recovery flags (3A):")
        for o in flags:
            lines.append(f"  - ({o.category}) {o.text}")

    lines.append(
        "Guidance: This athlete has recent recovery data (HRV / sleep). When that "
        "data signals suppressed recovery — short-term trajectory `fatigued` or "
        "`overreached`, HRV trending down, sleep debt, or an ACWR zone of "
        "`functional_overreach` / `non_functional_overreach` — PRIORITIZE recovery "
        "in this refresh: pull volume toward the lower edge of the band and cut "
        "intensity (bias Z1-Z2), unless a race-proximity constraint overrides. When "
        "the signals conflict, default to the more conservative load. When recovery "
        "is solid (`recovered` / `steady` / `building`, HRV and sleep intact), "
        "proceed with the planned progression — do not under-load a recovered "
        "athlete. This is a coaching judgment grounded in the data above, not a hard "
        "rule, and is separate from the calendar-driven deload cadence already noted "
        "above."
    )
    return lines
