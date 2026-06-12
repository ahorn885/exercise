"""Shared Layer-4 injury-accommodation prompt rendering.

Single source of truth for how Layer 2D's excluded + accommodated exercises
are rendered into a synthesizer prompt's "active injuries" block. Both the
plan-CREATE path (`layer4/per_phase.py`) and the plan-REFRESH path
(`layer4/plan_refresh_t1.py`, shared by T1/T2/T3) delegate here so the two
prompts can never drift.

#555 — previously each path rendered only the modality *type name*
(`", ".join(m.modality_type ...)`), so the synthesizer was told *that* an
exercise was accommodated but not *how much* (the params) or *why* (the
rationale). `format_modality` now renders each of the six modality variants
with its concrete parameters plus the rationale, so the model can actually
apply the prescribed modification instead of guessing.
"""

from __future__ import annotations

from typing import Any


def format_modality(m: Any) -> str:
    """Render one `AccommodationModality` as `type (params) — rationale`.

    Covers the six discriminated-union variants in `layer4/context.py`. Only
    populated params are shown (several variants have optional fields). The
    rationale is always appended so the synthesizer has the clinical "why".
    """
    mt = m.modality_type
    params: str | None = None

    if mt == "volume_reduction":
        params = f"×{m.factor:g} on {m.applies_to}"
    elif mt == "intensity_reduction":
        params = f"×{m.factor:g} of {m.target_metric}"
    elif mt == "tempo_modification":
        bits: list[str] = [m.tempo_pattern]
        for label, val in (
            ("eccentric_s", m.eccentric_s),
            ("iso_bottom_s", m.isometric_bottom_s),
            ("concentric_s", m.concentric_s),
            ("iso_top_s", m.isometric_top_s),
            ("hold_s", m.hold_s),
            ("sets", m.sets),
            ("rest_s", m.rest_s),
            ("intensity_pct_mvc", m.intensity_pct_mvc),
        ):
            if val is not None:
                bits.append(f"{label}={val}")
        params = ", ".join(bits)
    elif mt == "loading_type_change":
        params = f"{m.from_type}→{m.to_type}"
    elif mt == "frequency_reduction":
        bits = []
        if m.factor is not None:
            bits.append(f"×{m.factor:g}")
        if m.sessions_per_week_cap is not None:
            bits.append(f"cap {m.sessions_per_week_cap}/wk")
        if m.discipline_id is not None:
            bits.append(f"discipline {m.discipline_id}")
        params = ", ".join(bits)
    # exercise_substitution carries no params beyond the rationale.

    head = f"{mt} ({params})" if params else mt
    rationale = (m.rationale or "").strip()
    return f"{head} — {rationale}" if rationale else head


def format_active_injuries(
    layer2d: Any,
    *,
    none_payload_line: str,
    none_on_file_line: str,
) -> list[str]:
    """Render the active-injuries block from 2D excluded + accommodated lists.

    `none_payload_line` / `none_on_file_line` are passed by the caller so each
    prompt keeps its own empty-state wording while sharing the EXCLUDE /
    ACCOMMODATE line format (and the #555 modality detail).
    """
    if layer2d is None:
        return [none_payload_line]
    if not layer2d.excluded_exercises and not layer2d.accommodated_exercises:
        return [none_on_file_line]
    lines: list[str] = []
    for er in layer2d.excluded_exercises:
        lines.append(f"- EXCLUDE {er.exercise_id} ({er.exercise_name})")
    for er in layer2d.accommodated_exercises:
        mods = "; ".join(format_modality(m) for m in er.accommodations)
        lines.append(
            f"- ACCOMMODATE {er.exercise_id} ({er.exercise_name}): {mods}"
        )
    return lines
