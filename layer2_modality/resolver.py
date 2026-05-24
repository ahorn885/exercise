"""Best-Fit Modality resolver — `resolve_best_fit_modality`.

Per `aidstation-sources/BestFitModality_Spec_v1.md` (S1 spec shipped
2026-05-24; implementation slice ratified V1 = infra-only at the
AskUserQuestion gate — keeps the spec's 3 representative disciplines
verbatim; vocab population for the 9 deferred AR disciplines
(D-005/D-007/D-008a/D-008b/D-011/D-014/D-015/D-016/D-020) lands in
per-discipline follow-on slices ratified at AskUserQuestion gates per
spec §12 BM-1).

Pure-Python set arithmetic against a module-level
`_MODALITY_OPTIONS_PER_DISCIPLINE` dict — mirrors the gear-toggle /
skill-toggle precedent (`_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS` BucketC_g +
`_TOGGLE_ALSO_SATISFIES` Phase 2.4-Prep). No new DB schema; existing
Layer 1 + 2B + 2C cache eviction policies transitively force the
resolver to re-run on any input change (spec §9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from layer4.context import (
    Layer2ModalityPayload,
    ModalityCoachingFlag,
    ModalityOption,
    ModalityRecommendation,
)


class Layer2ModalityInputError(ValueError):
    """Raised when `resolve_best_fit_modality` preconditions fail.

    Per spec §4 — fail-loud at the resolver boundary rather than
    propagating malformed inputs into the menu logic.
    """


@dataclass(frozen=True)
class ClusterLocaleInput:
    """Per spec §3 — single-locale slice of the cluster's resolver input.

    Caller (`layer4.orchestrator._upstream_full_cone` +
    `orchestrate_single_session_synthesize`) constructs one entry per
    locale by zipping locale rows from Layer 1 with the per-locale
    `Layer2CPayload.effective_pool` outputs.
    """

    locale_id: str
    locale_name: str | None
    locale_terrain_ids: list[str]
    effective_pool: list[str]


@dataclass(frozen=True)
class ModalityOptionDef:
    """Module-level vocab entry per spec §5.1.

    Each discipline carrying a meaningful modality split owns a list
    of these in `_MODALITY_OPTIONS_PER_DISCIPLINE`. The resolver runs
    set arithmetic against the locale's terrain + equipment + the
    athlete's skill toggle states to decide which options survive
    into the menu.
    """

    modality_id: str
    modality_name: str
    requires_terrain_any_of: list[str] = field(default_factory=list)
    requires_equipment_all_of: list[str] = field(default_factory=list)
    requires_skill_toggle: str | None = None
    is_outdoor: bool = True
    is_specific: bool = True
    base_preference_score: int = 50
    rationale_template: str = ""


# ─── §5.1 module-level modality vocab ────────────────────────────────────────
#
# Representative AR subset per spec §5.1 + BM-1. Three disciplines
# carry concrete vocab as the load-bearing example for the
# implementation pattern; the remaining 9 AR disciplines
# (D-005/D-007/D-008a/D-008b/D-011/D-014/D-015/D-016/D-020) land in
# per-discipline follow-on slices ratified at AskUserQuestion gates
# per Trigger #2 padding scrutiny. D-013 Wilderness Navigation is
# intentionally absent — one fundamental modality (go outside and
# navigate); silent pass-through per spec §5.1.
#
# Equipment names use spec-literal canonical-style strings. Round-trip
# alignment with the active 0B `layer0.equipment_items.canonical_name`
# vocab is BM-5 (open). The static lint test
# (`tests/test_layer2_modality.py::TestStaticLint`) catches drift
# between module dict and known-canonical terrain + skill-toggle
# vocab today; full equipment canonicalisation lands with BM-5.

_MODALITY_OPTIONS_PER_DISCIPLINE: dict[str, list[ModalityOptionDef]] = {
    # D-001 Trail Running
    "D-001": [
        ModalityOptionDef(
            modality_id="outdoor_trail_run",
            modality_name="Outdoor trail run",
            requires_terrain_any_of=["TRN-002", "TRN-003", "TRN-004", "TRN-005", "TRN-006"],
            requires_equipment_all_of=[],
            requires_skill_toggle=None,
            is_outdoor=True,
            is_specific=True,
            base_preference_score=90,
            rationale_template="trail terrain accessible from {locale_name}",
        ),
        ModalityOptionDef(
            modality_id="outdoor_road_run",
            modality_name="Outdoor road run",
            requires_terrain_any_of=["TRN-001"],
            requires_equipment_all_of=[],
            requires_skill_toggle=None,
            is_outdoor=True,
            is_specific=False,
            base_preference_score=60,
            rationale_template="paved surface accessible; trail unavailable at {locale_name}",
        ),
        ModalityOptionDef(
            modality_id="treadmill_run",
            modality_name="Treadmill run (indoor)",
            requires_terrain_any_of=["TRN-016"],
            requires_equipment_all_of=["Treadmill"],
            requires_skill_toggle=None,
            is_outdoor=False,
            is_specific=False,
            base_preference_score=30,
            rationale_template="indoor substitute",
        ),
    ],
    # D-006 Outdoor Road Cycling (and gravel-fit variants)
    "D-006": [
        ModalityOptionDef(
            modality_id="outdoor_gravel_ride",
            modality_name="Outdoor gravel ride",
            requires_terrain_any_of=["TRN-020"],
            requires_equipment_all_of=["Gravel bike"],
            requires_skill_toggle=None,
            is_outdoor=True,
            is_specific=True,
            base_preference_score=85,
            rationale_template="gravel surface accessible from {locale_name}, gravel bike on hand",
        ),
        ModalityOptionDef(
            modality_id="outdoor_road_ride",
            modality_name="Outdoor road ride",
            requires_terrain_any_of=["TRN-001"],
            requires_equipment_all_of=["Road bike"],
            requires_skill_toggle=None,
            is_outdoor=True,
            is_specific=True,
            base_preference_score=80,
            rationale_template="paved surface accessible, road bike on hand",
        ),
        ModalityOptionDef(
            modality_id="indoor_trainer",
            modality_name="Indoor trainer workout",
            requires_terrain_any_of=["TRN-016"],
            requires_equipment_all_of=["Bike trainer"],
            requires_skill_toggle=None,
            is_outdoor=False,
            is_specific=False,
            base_preference_score=40,
            rationale_template="trainer substitute when outdoor unavailable",
        ),
    ],
    # D-010 Outdoor Rock Climbing (rope-options gated by climbing_roped)
    "D-010": [
        ModalityOptionDef(
            modality_id="outdoor_lead_climb",
            modality_name="Outdoor lead climb",
            requires_terrain_any_of=["TRN-013"],
            requires_equipment_all_of=["Rope", "Quickdraws", "Harness"],
            requires_skill_toggle="climbing_roped",
            is_outdoor=True,
            is_specific=True,
            base_preference_score=90,
            rationale_template="outdoor rock accessible, lead-climbing capability enabled",
        ),
        ModalityOptionDef(
            modality_id="outdoor_top_rope",
            modality_name="Outdoor top-rope climb",
            requires_terrain_any_of=["TRN-013"],
            requires_equipment_all_of=["Rope", "Harness"],
            requires_skill_toggle="climbing_roped",
            is_outdoor=True,
            is_specific=True,
            base_preference_score=80,
            rationale_template="outdoor rock accessible, rope capability enabled",
        ),
        ModalityOptionDef(
            modality_id="outdoor_boulder",
            modality_name="Outdoor bouldering",
            requires_terrain_any_of=["TRN-013"],
            requires_equipment_all_of=["Crash pad"],
            requires_skill_toggle=None,
            is_outdoor=True,
            is_specific=True,
            base_preference_score=70,
            rationale_template="outdoor rock accessible; no rope skill required for bouldering",
        ),
        ModalityOptionDef(
            modality_id="gym_lead_climb",
            modality_name="Gym lead climb",
            requires_terrain_any_of=["TRN-014"],
            requires_equipment_all_of=["Climbing gym membership"],
            requires_skill_toggle="climbing_roped",
            is_outdoor=False,
            is_specific=True,
            base_preference_score=60,
            rationale_template="climbing gym accessible, lead capability enabled",
        ),
        ModalityOptionDef(
            modality_id="gym_top_rope",
            modality_name="Gym top-rope",
            requires_terrain_any_of=["TRN-014"],
            requires_equipment_all_of=["Climbing gym membership"],
            requires_skill_toggle=None,
            is_outdoor=False,
            is_specific=True,
            base_preference_score=55,
            rationale_template="climbing gym top-rope; no lead capability required",
        ),
        ModalityOptionDef(
            modality_id="gym_boulder",
            modality_name="Gym bouldering",
            requires_terrain_any_of=["TRN-014"],
            requires_equipment_all_of=["Climbing gym membership"],
            requires_skill_toggle=None,
            is_outdoor=False,
            is_specific=True,
            base_preference_score=50,
            rationale_template="climbing gym bouldering substitute",
        ),
        ModalityOptionDef(
            modality_id="gym_hangboard",
            modality_name="Hangboard finger-strength",
            requires_terrain_any_of=["TRN-016"],
            requires_equipment_all_of=["Hangboard"],
            requires_skill_toggle=None,
            is_outdoor=False,
            is_specific=False,
            base_preference_score=30,
            rationale_template="finger-strength substitute when climbing terrain unavailable",
        ),
    ],
}


# ─── §4 input validation ─────────────────────────────────────────────────────


def _validate_inputs(
    cluster_locale_inputs: list[ClusterLocaleInput],
    included_discipline_ids: list[str],
    skill_toggle_states: dict[str, bool] | None,
    etl_version_set: dict[str, str],
) -> None:
    """Per spec §4 — fail-loud preconditions. Raises
    `Layer2ModalityInputError` on the first failure.
    """
    if not cluster_locale_inputs:
        raise Layer2ModalityInputError(
            "cluster_locale_inputs must be non-empty"
        )
    seen_ids: set[str] = set()
    for entry in cluster_locale_inputs:
        if not isinstance(entry, ClusterLocaleInput):
            raise Layer2ModalityInputError(
                f"cluster_locale_inputs entries must be ClusterLocaleInput; "
                f"got {type(entry).__name__}"
            )
        if not entry.locale_id or not isinstance(entry.locale_id, str):
            raise Layer2ModalityInputError(
                f"locale_id must be a non-empty string; got {entry.locale_id!r}"
            )
        if entry.locale_id in seen_ids:
            raise Layer2ModalityInputError(
                f"duplicate locale_id={entry.locale_id!r} in cluster_locale_inputs"
            )
        seen_ids.add(entry.locale_id)
        if not isinstance(entry.locale_terrain_ids, list) or not all(
            isinstance(t, str) for t in entry.locale_terrain_ids
        ):
            raise Layer2ModalityInputError(
                f"locale_terrain_ids for {entry.locale_id!r} must be list[str]"
            )
        if not isinstance(entry.effective_pool, list) or not all(
            isinstance(e, str) for e in entry.effective_pool
        ):
            raise Layer2ModalityInputError(
                f"effective_pool for {entry.locale_id!r} must be list[str]"
            )
    if not included_discipline_ids:
        raise Layer2ModalityInputError(
            "included_discipline_ids must be non-empty"
        )
    for d_id in included_discipline_ids:
        # Per spec §4 condition 5, but relaxed to "non-empty string"
        # since the resolver silently skips disciplines not in
        # `_MODALITY_OPTIONS_PER_DISCIPLINE` (§5.1) — strict shape
        # validation gains nothing actionable and only forces the
        # orchestrator's synthetic test fixtures to mirror canonical
        # shape unnecessarily. The dict keys ARE canonical-shape;
        # callers passing non-canonical ids get silent pass-through.
        if not isinstance(d_id, str) or not d_id:
            raise Layer2ModalityInputError(
                f"included_discipline_ids entry must be a non-empty string; "
                f"got {d_id!r}"
            )
    if skill_toggle_states is not None:
        if not isinstance(skill_toggle_states, dict):
            raise Layer2ModalityInputError(
                "skill_toggle_states must be dict[str, bool] or None"
            )
        for k, v in skill_toggle_states.items():
            if not isinstance(k, str):
                raise Layer2ModalityInputError(
                    f"skill_toggle_states key {k!r} must be str"
                )
            if not isinstance(v, bool):
                raise Layer2ModalityInputError(
                    f"skill_toggle_states[{k!r}] must be bool; got {type(v).__name__}"
                )
    if not isinstance(etl_version_set, dict):
        raise Layer2ModalityInputError(
            "etl_version_set must be a dict"
        )
    for required_key in ("0A", "0B", "0C"):
        if required_key not in etl_version_set:
            raise Layer2ModalityInputError(
                f"etl_version_set missing required key {required_key!r}"
            )


# ─── §3 discipline-name lookup ───────────────────────────────────────────────


def _load_discipline_info(
    db: Any,
    discipline_ids: list[str],
    version_0a: str,
) -> dict[str, str]:
    """Map each `D-xxx` id to its canonical discipline name via
    `layer0.sport_discipline_bridge`. Mirrors
    `layer2c.builder._load_discipline_info` — a discipline may appear
    under multiple framework_sports; first-row-wins deterministically.

    Returns `{discipline_id: discipline_name}`. Missing ids fall back
    to the discipline_id itself so the payload still surfaces the row;
    the orchestrator's upstream `included_discipline_ids` is sourced
    from the same table, so misses should not happen in practice.
    """
    if not discipline_ids:
        return {}
    cur = db.execute(
        """
        SELECT discipline_id, discipline_name
          FROM layer0.sport_discipline_bridge
         WHERE discipline_id = ANY(?)
           AND etl_version = ?
           AND superseded_at IS NULL
        """,
        (list(discipline_ids), version_0a),
    )
    info: dict[str, str] = {}
    for row in cur.fetchall():
        d_id = row["discipline_id"]
        if d_id not in info:
            info[d_id] = row["discipline_name"]
    for d_id in discipline_ids:
        info.setdefault(d_id, d_id)
    return info


# ─── §5.2 / §5.4 menu construction ───────────────────────────────────────────


def _resolve_menu_for_pair(
    opt_defs: list[ModalityOptionDef],
    locale: ClusterLocaleInput,
    skill_toggle_states: dict[str, bool],
) -> list[ModalityOption]:
    """Per spec §5.2. Return the satisfied modality options for one
    `(discipline, locale)` pair, sorted by `(-preference_score,
    modality_id)` for deterministic ordering.
    """
    terrain_set = set(locale.locale_terrain_ids)
    pool_set = set(locale.effective_pool)
    menu: list[ModalityOption] = []
    for opt in opt_defs:
        if opt.requires_terrain_any_of:
            terrain_match = set(opt.requires_terrain_any_of) & terrain_set
            terrain_ok = bool(terrain_match)
        else:
            terrain_match = set()
            terrain_ok = True
        if opt.requires_equipment_all_of:
            equip_ok = set(opt.requires_equipment_all_of).issubset(pool_set)
        else:
            equip_ok = True
        if opt.requires_skill_toggle is None:
            skill_ok = True
        else:
            skill_ok = skill_toggle_states.get(opt.requires_skill_toggle) is True
        if not (terrain_ok and equip_ok and skill_ok):
            continue
        rationale = opt.rationale_template.format(
            locale_name=locale.locale_name or locale.locale_id
        )
        menu.append(
            ModalityOption(
                modality_id=opt.modality_id,
                modality_name=opt.modality_name,
                preference_score=opt.base_preference_score,
                is_outdoor=opt.is_outdoor,
                is_specific=opt.is_specific,
                rationale_hint=rationale,
                satisfied_terrain=sorted(terrain_match),
                satisfied_equipment=list(opt.requires_equipment_all_of),
                satisfied_skill=opt.requires_skill_toggle,
            )
        )
    menu.sort(key=lambda m: (-m.preference_score, m.modality_id))
    return menu


# ─── §8 coaching-flag emission ───────────────────────────────────────────────


def _emit_coaching_flags(
    *,
    recommendations: list[ModalityRecommendation],
    discipline_info: dict[str, str],
    cluster_locale_inputs: list[ClusterLocaleInput],
    skill_toggle_states: dict[str, bool],
) -> list[ModalityCoachingFlag]:
    """Per spec §8 — three flag triggers consolidated:

    - §8.1 `no_modality_recommendation` — cluster-wide; fires when
      every option for a discipline (that IS in the dict) is
      unsatisfied at EVERY locale.
    - §8.2 `only_generic_modality_available` — per-discipline; fires
      when at least one locale resolves a modality but none of the
      resolved options carry `is_specific=True`.
    - §8.3 `skill_capability_blocks_specific_modality` — per
      `(discipline, locale, blocking_skill)` triplet; fires when a
      skill-gated specific option WOULD be satisfied on terrain +
      equipment but the toggle is OFF.
    """
    flags: list[ModalityCoachingFlag] = []

    # Index recommendations by discipline for cluster-wide rollups.
    by_discipline: dict[str, list[ModalityRecommendation]] = {}
    for rec in recommendations:
        by_discipline.setdefault(rec.discipline_id, []).append(rec)

    # 8.1 + 8.2 — discipline-level rollup
    for d_id, rec_list in by_discipline.items():
        non_empty_locales = [r for r in rec_list if r.menu]
        if not non_empty_locales:
            # No menu at ANY locale → cluster-wide flag
            missing_terrain: set[str] = set()
            missing_equipment: set[str] = set()
            missing_skill: set[str] = set()
            for opt in _MODALITY_OPTIONS_PER_DISCIPLINE.get(d_id, []):
                missing_terrain.update(opt.requires_terrain_any_of)
                missing_equipment.update(opt.requires_equipment_all_of)
                if opt.requires_skill_toggle:
                    missing_skill.add(opt.requires_skill_toggle)
            flags.append(
                ModalityCoachingFlag(
                    flag_type="no_modality_recommendation",
                    discipline_id=d_id,
                    discipline_name=discipline_info.get(d_id, d_id),
                    locale_id=None,
                    locale_name=None,
                    message=(
                        f"You included {discipline_info.get(d_id, d_id)} but no locale "
                        f"in your cluster has a satisfying modality. Consider adding "
                        f"compatible terrain, equipment, or a locale with that capability."
                    ),
                    metadata={
                        "missing_terrain": sorted(missing_terrain),
                        "missing_equipment": sorted(missing_equipment),
                        "missing_skill": sorted(missing_skill) if missing_skill else None,
                    },
                )
            )
            continue
        any_specific = any(
            any(opt.is_specific for opt in r.menu) for r in non_empty_locales
        )
        if not any_specific:
            first_resolved = non_empty_locales[0]
            satisfied_generic = [
                opt.modality_id for opt in first_resolved.menu
            ]
            unsatisfied_specific: list[str] = []
            for opt in _MODALITY_OPTIONS_PER_DISCIPLINE.get(d_id, []):
                if opt.is_specific:
                    unsatisfied_specific.append(opt.modality_id)
            specific_missing_terrain: set[str] = set()
            specific_missing_equipment: set[str] = set()
            for opt in _MODALITY_OPTIONS_PER_DISCIPLINE.get(d_id, []):
                if opt.is_specific:
                    specific_missing_terrain.update(opt.requires_terrain_any_of)
                    specific_missing_equipment.update(opt.requires_equipment_all_of)
            flags.append(
                ModalityCoachingFlag(
                    flag_type="only_generic_modality_available",
                    discipline_id=d_id,
                    discipline_name=discipline_info.get(d_id, d_id),
                    locale_id=first_resolved.locale_id,
                    locale_name=first_resolved.locale_name,
                    message=(
                        f"You included {discipline_info.get(d_id, d_id)} but only "
                        f"generic / substitute modalities resolve at your locales. "
                        f"Specific outdoor stimulus will be limited."
                    ),
                    metadata={
                        "specific_options_unavailable": unsatisfied_specific,
                        "generic_options_available": satisfied_generic,
                        "missing_terrain": sorted(specific_missing_terrain),
                        "missing_equipment": sorted(specific_missing_equipment),
                    },
                )
            )

    # 8.3 — per-(discipline, locale, blocking_skill)
    for locale in cluster_locale_inputs:
        terrain_set = set(locale.locale_terrain_ids)
        pool_set = set(locale.effective_pool)
        for d_id in by_discipline.keys():
            opt_defs = _MODALITY_OPTIONS_PER_DISCIPLINE.get(d_id, [])
            for opt in opt_defs:
                if opt.requires_skill_toggle is None or not opt.is_specific:
                    continue
                if skill_toggle_states.get(opt.requires_skill_toggle) is True:
                    continue
                terrain_ok = (
                    bool(set(opt.requires_terrain_any_of) & terrain_set)
                    if opt.requires_terrain_any_of
                    else True
                )
                equip_ok = (
                    set(opt.requires_equipment_all_of).issubset(pool_set)
                    if opt.requires_equipment_all_of
                    else True
                )
                if not (terrain_ok and equip_ok):
                    continue
                # Find the current top-pick for this (discipline, locale)
                # so coach-voice copy can name the downgrade.
                current_rec = next(
                    (
                        r for r in by_discipline[d_id]
                        if r.locale_id == locale.locale_id
                    ),
                    None,
                )
                resolves_to = (
                    current_rec.top_pick_modality_id
                    if current_rec is not None
                    else None
                )
                flags.append(
                    ModalityCoachingFlag(
                        flag_type="skill_capability_blocks_specific_modality",
                        discipline_id=d_id,
                        discipline_name=discipline_info.get(d_id, d_id),
                        locale_id=locale.locale_id,
                        locale_name=locale.locale_name,
                        message=(
                            f"{opt.modality_name} is a best-fit option for "
                            f"{discipline_info.get(d_id, d_id)} at "
                            f"{locale.locale_name or locale.locale_id} but requires the "
                            f"{opt.requires_skill_toggle!r} skill toggle, which is "
                            f"currently OFF. Enable it on Profile → Skills if you have "
                            f"that experience."
                        ),
                        metadata={
                            "blocked_modality_id": opt.modality_id,
                            "blocking_skill_toggle": opt.requires_skill_toggle,
                            "currently_resolves_to": resolves_to,
                        },
                    )
                )

    return flags


# ─── public entry point ──────────────────────────────────────────────────────


def resolve_best_fit_modality(
    db: Any,
    *,
    cluster_locale_inputs: list[ClusterLocaleInput],
    included_discipline_ids: list[str],
    skill_toggle_states: dict[str, bool] | None = None,
    etl_version_set: dict[str, str],
) -> Layer2ModalityPayload:
    """Per `BestFitModality_Spec_v1.md` §3.

    Returns a `Layer2ModalityPayload` carrying one
    `ModalityRecommendation` per `(discipline, locale)` pair plus any
    coaching flags. Pure-Python; no LLM call; <100ms typical budget
    for a 3-locale × 12-discipline cluster including the single
    discipline-name SELECT (§11).

    Disciplines absent from `_MODALITY_OPTIONS_PER_DISCIPLINE` (those
    with no meaningful modality split — e.g. D-013 Wilderness
    Navigation) silently produce no recommendation rows; Layer 4
    falls back to its current freeform reasoning for those.
    """
    _validate_inputs(
        cluster_locale_inputs,
        included_discipline_ids,
        skill_toggle_states,
        etl_version_set,
    )
    skill_states = dict(skill_toggle_states) if skill_toggle_states else {}

    version_0a = etl_version_set["0A"]
    discipline_info = _load_discipline_info(
        db, included_discipline_ids, version_0a
    )

    recommendations: list[ModalityRecommendation] = []
    for d_id in included_discipline_ids:
        opt_defs = _MODALITY_OPTIONS_PER_DISCIPLINE.get(d_id)
        if opt_defs is None:
            # Discipline carries no meaningful modality split — silent
            # pass-through per spec §5.1.
            continue
        for locale in cluster_locale_inputs:
            menu = _resolve_menu_for_pair(opt_defs, locale, skill_states)
            top_pick_modality_id = menu[0].modality_id if menu else None
            rationale_hint = menu[0].rationale_hint if menu else None
            recommendations.append(
                ModalityRecommendation(
                    discipline_id=d_id,
                    discipline_name=discipline_info.get(d_id, d_id),
                    locale_id=locale.locale_id,
                    locale_name=locale.locale_name,
                    menu=menu,
                    top_pick_modality_id=top_pick_modality_id,
                    rationale_hint=rationale_hint,
                )
            )

    coaching_flags = _emit_coaching_flags(
        recommendations=recommendations,
        discipline_info=discipline_info,
        cluster_locale_inputs=cluster_locale_inputs,
        skill_toggle_states=skill_states,
    )

    return Layer2ModalityPayload(
        etl_version_set=dict(etl_version_set),
        recommendations=recommendations,
        coaching_flags=coaching_flags,
    )
