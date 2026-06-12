"""Training-substitution resolver — `resolve_training_substitution`.

Per `aidstation-sources/designs/BestFitModality_Spec_v4.md` §5 (re-model Slice 5,
2026-05-25). This is the *re-model* of the best-fit node: given a race
described per-discipline (craft + terrain breakdown), it produces a
per-discipline training-substitution brief — the closest trainable terrain
emphasis (ranked by `pct × fidelity`), the untrainable-terrain gaps, and the
craft candidate set the Layer 4 LLM picks from.

Design (ratified at the Slice 5 gate, 2026-05-25):
- **Terrain proxy work is delegated to Layer 2B** (§3): this node consumes the
  already-computed `Layer2BPayload.terrain_by_discipline` blocks (Slice 4)
  rather than re-deriving proxies — no extra SQL, no `db` param.
- **Craft candidates are handed to the LLM** (R1 / gate Q2): the full set of
  the athlete's owned crafts is surfaced verbatim; this node does NOT score or
  family-filter them. Craft closeness ("kayak ≈ packraft") is reasoned LLM-side
  in Layer 4. No new craft-family vocab (the §14 escape hatch — add a
  deterministic family table later only if the LLM over-substitutes).
Pure-Python assembly; no LLM call here (§11 — the craft reasoning rides inside
the existing Layer 4 synthesis call).
"""

from __future__ import annotations

from layer4.context import (
    Layer2BDisciplineBlock,
    TerrainEmphasis,
    TerrainGapRef,
    TrainingSubstitution,
    TrainingSubstitutionFlag,
    TrainingSubstitutionPayload,
)

from discipline_display_names import discipline_display_name


class Layer2ModalityInputError(ValueError):
    """Raised when `resolve_training_substitution` preconditions fail.

    Fail-loud at the resolver boundary rather than propagating malformed
    inputs into the substitution logic.
    """


# Terrains whose best local proxy is unbridgeable, undefined, or below this
# fidelity are emitted as untrainable-terrain gaps rather than emphasis
# (§5.1). A proxy with fidelity in `[floor, low_threshold)` still earns
# emphasis but raises a `terrain_low_fidelity` flag. Aligned with the 2B
# severity banding (0.60 → medium, 0.40 → high, 0.30 → critical).
_UNTRAINABLE_FIDELITY_FLOOR = 0.25
_LOW_FIDELITY_THRESHOLD = 0.60


def resolve_training_substitution(
    *,
    terrain_by_discipline: list[Layer2BDisciplineBlock],
    athlete_crafts: list[str],
    etl_version_set: dict[str, str],
    discipline_names: dict[str, str] | None = None,
    fidelity_floor: float = _UNTRAINABLE_FIDELITY_FLOOR,
    low_fidelity_threshold: float = _LOW_FIDELITY_THRESHOLD,
    discipline_modality_groups: dict[str, list[str]] | None = None,
    craft_discipline_aliases: dict[str, list[str]] | None = None,
) -> TrainingSubstitutionPayload:
    """Per `BestFitModality_Spec_v4.md` §5.

    Args:
        terrain_by_discipline: Layer 2B per-discipline terrain blocks (Slice 4
            output). One `TrainingSubstitution` is emitted per block.
        athlete_crafts: every craft the athlete owns (paddle + bike today),
            deduped. Surfaced verbatim as the candidate set; the LLM picks.
        etl_version_set: provenance triplet, carried for cache/determinism.
        discipline_names: optional `discipline_id -> bridge name` fallback for
            the pure-craft label (defaults to the curated display-name map).
        fidelity_floor: below this a proxy is untrainable (§5.1).
        low_fidelity_threshold: a proxy below this raises `terrain_low_fidelity`.
        discipline_modality_groups: X1b.3b — `{discipline_id: [group_id, ...]}`
            from `layer0.discipline_modality_membership`. When supplied with
            `craft_discipline_aliases`, the candidate craft set is narrowed
            per craft-based discipline to crafts that share a modality group
            with it (Modality_Group_Spec §6). Both None → today's behavior.
        craft_discipline_aliases: X1b.3b — `{craft_name: [discipline_id, ...]}`
            from `layer0.craft_discipline_aliases` (many-to-many).

    Returns a `TrainingSubstitutionPayload`; pure-Python, no LLM, no DB.
    """
    if not isinstance(etl_version_set, dict) or not etl_version_set:
        raise Layer2ModalityInputError(
            "etl_version_set must be a non-empty dict for provenance"
        )

    names = discipline_names or {}
    candidate_crafts = sorted(set(athlete_crafts))

    # X1b.3b — craft → modality-group narrowing (Modality_Group_Spec §6). When
    # both maps are present, narrow the per-discipline candidate crafts to those
    # whose aliased discipline(s) share a modality group with the block's
    # discipline. `_craft_relevant_groups` is the universe of groups reachable
    # from any owned craft, so the narrowing only fires on craft-based
    # disciplines (a foot/swim/climb block is left untouched — no craft applies,
    # and it is NOT a craft_unavailable case). Both maps None → pre-X1b.3b.
    _disc_groups = discipline_modality_groups or {}
    _craft_aliases = craft_discipline_aliases or {}
    _filter_crafts = bool(_disc_groups and _craft_aliases and candidate_crafts)
    _craft_groups = {
        c: {g for d in _craft_aliases.get(c, []) for g in _disc_groups.get(d, [])}
        for c in candidate_crafts
    }
    # The universe of craft-trainable groups comes from the FULL alias table
    # (not just owned crafts) — otherwise a bike discipline would look
    # non-craft-relevant to a paddle-only athlete and skip the narrowing,
    # leaving a kayak wrongly surfaced as a mountain-bike substitute.
    _craft_relevant_groups: set[str] = {
        g
        for discs in _craft_aliases.values()
        for d in discs
        for g in _disc_groups.get(d, [])
    }

    recommendations: list[TrainingSubstitution] = []
    flags: list[TrainingSubstitutionFlag] = []

    for block in terrain_by_discipline:
        d_id = block.discipline_id
        d_name = discipline_display_name(d_id, fallback=names.get(d_id))

        # X1b.3b — narrow candidate crafts to those sharing a modality group
        # with this discipline (craft-based disciplines only).
        block_candidates = candidate_crafts
        if _filter_crafts:
            target_groups = set(_disc_groups.get(d_id, []))
            if target_groups & _craft_relevant_groups:
                filtered = [
                    c for c in candidate_crafts if target_groups & _craft_groups[c]
                ]
                if filtered != candidate_crafts:
                    if filtered:
                        flags.append(
                            TrainingSubstitutionFlag(
                                flag_type="craft_substitution",
                                discipline_id=d_id,
                                discipline_name=d_name,
                                message=(
                                    f"Craft substitution for {d_name} narrowed to "
                                    f"same-modality crafts: {', '.join(filtered)}."
                                ),
                                metadata={
                                    "candidate_crafts": filtered,
                                    "all_crafts": list(candidate_crafts),
                                },
                            )
                        )
                    else:
                        flags.append(
                            TrainingSubstitutionFlag(
                                flag_type="craft_unavailable",
                                discipline_id=d_id,
                                discipline_name=d_name,
                                message=(
                                    f"You own no craft in the same modality group as "
                                    f"{d_name} — sessions will reason from the "
                                    f"discipline label alone."
                                ),
                                metadata={"all_crafts": list(candidate_crafts)},
                            )
                        )
                block_candidates = filtered

        emphasis: list[TerrainEmphasis] = []
        untrainable: list[TerrainGapRef] = []

        for rt in block.race_terrain:
            if rt.available_locally:
                emphasis.append(
                    TerrainEmphasis(
                        race_terrain_id=rt.terrain_id,
                        terrain_name=rt.terrain_name,
                        pct=rt.pct_of_race,
                        proxy_terrain_id=rt.terrain_id,
                        proxy_terrain_name=rt.terrain_name,
                        fidelity=1.0,
                        gap_severity="none",
                        proxy_methods=[],
                        uncoverable_stimulus=[],
                        emphasis_score=rt.pct_of_race,
                    )
                )
                continue

            gap = rt.gap
            untrainable_reason = _untrainable_reason(gap, fidelity_floor)
            if untrainable_reason is not None:
                untrainable.append(
                    TerrainGapRef(
                        race_terrain_id=rt.terrain_id,
                        terrain_name=rt.terrain_name,
                        pct=rt.pct_of_race,
                        gap_severity=gap.gap_severity if gap else "undefined",
                        reason=untrainable_reason,
                    )
                )
                flags.append(
                    TrainingSubstitutionFlag(
                        flag_type="terrain_untrainable",
                        discipline_id=d_id,
                        discipline_name=d_name,
                        race_terrain_id=rt.terrain_id,
                        message=(
                            f"{rt.pct_of_race:g}% of the {d_name} leg is on "
                            f"{rt.terrain_name or rt.terrain_id}, which has no usable "
                            f"local proxy ({untrainable_reason}) — compensate."
                        ),
                        metadata={
                            "pct": rt.pct_of_race,
                            "gap_severity": gap.gap_severity if gap else "undefined",
                        },
                    )
                )
                continue

            # gap with a usable proxy
            fidelity = gap.proxy_fidelity  # not None past _untrainable_reason
            emphasis.append(
                TerrainEmphasis(
                    race_terrain_id=rt.terrain_id,
                    terrain_name=rt.terrain_name,
                    pct=rt.pct_of_race,
                    proxy_terrain_id=gap.proxy_terrain_id,
                    proxy_terrain_name=gap.proxy_terrain_name,
                    fidelity=fidelity,
                    gap_severity=gap.gap_severity,
                    proxy_methods=list(gap.proxy_methods),
                    uncoverable_stimulus=list(gap.uncoverable_stimulus),
                    emphasis_score=rt.pct_of_race * fidelity,
                )
            )
            if fidelity < low_fidelity_threshold:
                flags.append(
                    TrainingSubstitutionFlag(
                        flag_type="terrain_low_fidelity",
                        discipline_id=d_id,
                        discipline_name=d_name,
                        race_terrain_id=rt.terrain_id,
                        message=(
                            f"{d_name} {rt.terrain_name or rt.terrain_id}: best local "
                            f"proxy is {gap.proxy_terrain_name or gap.proxy_terrain_id} "
                            f"at fidelity {fidelity:.2f} — allow adaptation time."
                        ),
                        metadata={
                            "proxy_terrain_id": gap.proxy_terrain_id,
                            "fidelity": fidelity,
                            "adaptation_weeks_low": gap.adaptation_weeks_low,
                            "adaptation_weeks_high": gap.adaptation_weeks_high,
                        },
                    )
                )

        # Highest-value trainable chunk first (§5.1). Tie-break by raw pct then
        # terrain id for a stable order.
        emphasis.sort(
            key=lambda e: (-e.emphasis_score, -e.pct, e.race_terrain_id)
        )

        recommendations.append(
            TrainingSubstitution(
                discipline_id=d_id,
                discipline_name=d_name,
                race_craft=d_name,
                candidate_training_crafts=list(block_candidates),
                terrain_emphasis=emphasis,
                untrainable_terrain=untrainable,
            )
        )

    # §8.1 craft_unavailable — the athlete logged no crafts at all, so the
    # candidate set is empty for every discipline. Emitted once (no
    # craft-family map to scope it per-discipline; gate Q2 chose LLM-side
    # craft reasoning over a deterministic family table).
    if recommendations and not candidate_crafts:
        flags.append(
            TrainingSubstitutionFlag(
                flag_type="craft_unavailable",
                message=(
                    "No crafts are logged in your profile, so craft-specific "
                    "substitution can't be computed — sessions will reason from "
                    "the discipline labels alone."
                ),
                metadata={
                    "included_discipline_ids": [r.discipline_id for r in recommendations]
                },
            )
        )

    return TrainingSubstitutionPayload(
        etl_version_set=dict(etl_version_set),
        recommendations=recommendations,
        coaching_flags=flags,
    )


def _untrainable_reason(gap, fidelity_floor: float) -> str | None:
    """Return why a non-local terrain is untrainable, or None if its proxy is
    usable. Mirrors §5.1's untrainable test."""
    if gap is None:
        return "no proxy data"
    if gap.proxy_terrain_id is None or gap.gap_severity == "unbridgeable":
        return "unbridgeable"
    if gap.proxy_fidelity is None:
        return "undefined proxy fidelity"
    if gap.proxy_fidelity < fidelity_floor:
        return f"proxy fidelity {gap.proxy_fidelity:.2f} below floor {fidelity_floor:.2f}"
    return None
