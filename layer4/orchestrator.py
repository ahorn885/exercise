"""Layer 4 orchestrator — Phase 5.1 race_week_brief + Phase 5.2 single_session +
plan_refresh + plan_create.

End-to-end composition of the v2 upstream pipeline. Four entry points:

    `orchestrate_race_week_brief` (Phase 5.1, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_race_week_brief_cached

    `orchestrate_single_session_synthesize` (Phase 5.2, slice 1, 2026-05-20):
        Layer 1 → 2A → 2D → 2C (locale-only) → 3A →
        llm_layer4_single_session_synthesize_cached

    `orchestrate_plan_refresh` (Phase 5.2, slice 2, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_plan_refresh_cached
        (driver dispatches T1/T2/T3 internally; T3 cross-phase routes to
        Pattern A via `_route_t3_cross_phase_to_pattern_a`)

    `orchestrate_plan_create` (Phase 5.2, slice 3, 2026-05-20):
        Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → llm_layer4_plan_create_cached
        (Pattern A — per-phase synthesis loop + seam reviews internal to the
        driver; cached wrapper composes the per-entry §9.1 cache key)

Race_week_brief, plan_refresh, and plan_create share the full upstream cone
via the private `_upstream_full_cone` helper extracted at slice 2 (D1). The
helper covers the 3 shared pre-flight gates
(`etl_version_set_undiscoverable`, `framework_sport_missing`,
`primary_locale_missing`) plus the Layer 1 → 2A → 2B → 2D → 2C → 3A → 3B →
2E composition. Race_week_brief retains its two brief-specific cheap pre-LLM
gates inline (`no_target_event` + `race_week_brief_too_early`);
plan_refresh and plan_create skip both (no-event mode is supported;
refresh/create fire on demand, not on a calendar window).

Single-session's cone is materially narrower (no 2B / 2E / 3B, uses
`request.sport` not `primary_sport`, uses `request.locale_slug` not the
hard-coded `'home'`, and skips Layer 2C entirely on the quick_equipment
path) — too many points of divergence to share `_upstream_full_cone`, so
it stays inline.

See `Upstream_Implementation_Plan_v1.md` §4 rows 5.1 + 5.2 + `Layer4_Spec.md`
§3.1 / §3.2 / §3.3 / §3.4 / §4.5 for the entry-point contracts.

Vertical-slice limitations carried as forward-pointers:
- Layer 2B inputs now flow end-to-end per Phase 5.1 form-refresh A/B/C
  (2026-05-20): `race_terrain` from `RaceEventPayload.race_terrain`
  (Form-refresh A + B, Open Item 2B-3 closed); `locale_terrain_ids` from
  the home `locale_profiles.locale_terrain_ids` TEXT[] column (Form-refresh
  C, Open Item 2B-2 closed). Athletes who haven't yet captured race
  terrain surface as `race_terrain=[]`, which Layer 2B's loosened
  `_validate_inputs` accepts and emits a `race_terrain_unset` coaching
  flag instead of failing (paired loosen shipped with Form-refresh C).
  No-event-mode plan_refresh + plan_create calls pass `race_terrain=[]`
  for the same reason (no target race → empty terrain input). Multi-locale
  cluster union for `locale_terrain_ids` remains spec §3 future work (v1
  wires the home locale only).
- `prior_plan_session_window` + `plan_version_id` + `plan_version_id_parent`
  + `parsed_intent` + `plan_start_date` are caller-supplied kwargs on
  `orchestrate_plan_refresh` + `orchestrate_plan_create` pending the
  D-64 caller-side route + `plan_versions` table (matches the slice 1 D4
  precedent for D-63's `suggestion_id`). Race_week_brief now resolves both
  from the athlete's active plan internally (#732 slice 1): the prior Taper
  window is the currently-scheduled sessions through the event date and
  `plan_version_id` is the active plan version — the placeholders are gone.
- Layer 3A + Layer 3B run through the cached wrappers
  (`layer3a.cached_wrapper.llm_layer3a_athlete_state_cached` +
  `layer3b.cached_wrapper.llm_layer3b_goal_timeline_viability_cached`)
  as of Phase 5.2 Layer 3 caching slice (2026-05-21). The wrappers reuse
  the shared `layer4_cache` table via `cache.backend` and per-layer
  invalidation policy lives in `layer4.cache_invalidation` per the
  extended §9.3 matrix. Wiring covers all 4 entry points (3A+3B in
  `_upstream_full_cone`; 3A only in `orchestrate_single_session_synthesize`
  since single_session doesn't consume 3B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal

from layer1.builder import build_layer1_payload
from layer2_modality import resolve_training_substitution
from layer2a.builder import Layer2AInputError, q_layer2a_discipline_classifier_payload
from layer2b.builder import q_layer2b_terrain_classifier_payload
from layer2c.builder import q_layer2c_equipment_mapper_payload
from layer2d.builder import q_layer2d_injury_risk_profile_payload
from layer2e.builder import q_layer2e_nutrition_baseline_payload
from layer3a.cached_wrapper import llm_layer3a_athlete_state_cached
from layer3a.integration import assemble_layer3a_integration_bundle
from layer3b.cached_wrapper import llm_layer3b_goal_timeline_viability_cached
from layer4.cache import Layer4Cache
from layer4.cached_wrappers import (
    llm_layer4_plan_create_cached,
    llm_layer4_plan_refresh_cached,
    llm_layer4_race_week_brief_cached,
    llm_layer4_single_session_synthesize_cached,
)
from layer4.locale_assign import assign_locales
from layer4.rx_wire import apply_current_rx
from layer4.context import (
    Layer1Payload,
    Layer2APayload,
    Layer2BPayload,
    Layer2Bundle,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer2ETargetEvent,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    RaceEventPayload,
    TrainingSubstitutionPayload,
)
from layer4.payload import Layer4Payload, PlanSession
from layer4.hashing import compute_event_windows_hash
from layer4.phase_structure import phase_structure_from_3b
from layer4.plan_create import _compute_total_weeks
from layer4.session_feasibility import (
    EventWindowOverride,
    EventWindowSegment,
    TerrainResolution,
    enrich_resolution_display,
    indoor_machines,
    required_terrains,
    resolve_craft_terrain_feasibility,
    resolve_terrain_feasibility,
    segment_window_boundaries,
)
from layer4.single_session import SingleSessionRequest
from layer4.validator import skill_gated_disciplines
import locations
from athlete_event_windows_repo import load_event_windows
from athlete_craft_locale_repo import load_craft_locales
from race_events_repo import load_target_race_event_payload


_AUTO_FIRE_DAYS_TO_EVENT_MAX = 14

# Coarse race-format-based duration estimate for Layer 2E's TargetEvent
# (estimated_duration_hr > 0 is required). FALLBACK ONLY — the per-race
# `estimated_duration_hr` column (FormRefresh A1) is now the primary
# source; this map fires only when the athlete left duration blank.
# continuous_multi_day spans ~24h (continuous ultra) to 100h+ (expedition
# AR), so 48 is a deliberately mid-range placeholder pending the explicit
# value.
_DURATION_HR_BY_RACE_FORMAT: dict[str, float] = {
    "single_day": 8.0,
    "stage_race": 24.0,
    "continuous_multi_day": 48.0,
}


class OrchestrationError(RuntimeError):
    """Pre-flight / upstream-discovery error before any LLM call.

    Distinct from `Layer4InputError` (Layer-4-internal preconditions raised
    by `llm_layer4_race_week_brief`'s `_validate_inputs`); `OrchestrationError`
    surfaces when the orchestrator's own composition cannot proceed — no
    target race, no primary locale, etl_version_set undiscoverable,
    out-of-window auto-fire, etc.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class _UpstreamFullCone:
    """Composed upstream-payload set returned by `_upstream_full_cone`.

    Shared by `orchestrate_race_week_brief` + `orchestrate_plan_refresh` —
    the two full-cone entry points. Single_session is NOT a consumer (its
    narrower cone has too many divergence points to fit a shared helper —
    see module docstring for the cone-shape variance).

    Field shapes match the upstream payload types verbatim; consumers
    reshape into entry-point-specific kwargs (e.g., plan_refresh packs all 5
    layer-2 payloads into a `Layer2Bundle`). `layer2c_payloads` is already the
    per-locale dict the validator + locale-assign consume (#780 — one 2C
    resolution per cluster locale, not a single primary-only entry).
    """

    etl_version_set: dict[str, str]
    framework_sport: str
    primary_locale: str
    layer1_payload: Layer1Payload
    layer2a_payload: Layer2APayload
    layer2b_payload: Layer2BPayload
    # #780 — one Layer 2C payload per cluster locale (keyed by locale_id), each
    # resolved against THAT locale's own effective equipment. The validator's
    # cluster check + the locale-assign candidate set are keyed off this dict, so
    # every saved locale is in-cluster (was: a single primary-only entry carrying
    # the cluster-union pool — the documented stub that made nearby venues look
    # "not in cluster"). The primary entry is always present (cluster[0] is the
    # preferred locale; empty-cluster cones fall back to {primary_locale}).
    layer2c_payloads: dict[str, Layer2CPayload]
    layer2d_payload: Layer2DPayload
    layer2e_payload: Layer2EPayload
    # Training-substitution resolver output (terrain emphasis + craft candidate
    # set per discipline), consuming the Layer 2B `terrain_by_discipline`
    # blocks. Threaded into the race_week_brief + plan_create + plan_refresh
    # prompts + cache keys.
    training_substitution_payload: TrainingSubstitutionPayload
    layer3a_payload: Layer3APayload
    layer3b_payload: Layer3BPayload


def _collect_athlete_crafts(layer1_payload: Layer1Payload) -> list[str]:
    """Flatten the athlete's owned crafts across discipline baselines.

    Today only paddle + bike baselines carry craft inventories; the
    training-substitution resolver hands the union to the Layer 4 LLM as the
    candidate set (gate Q2 — no family filtering here). Deduped + sorted for a
    stable cache hash.
    """
    crafts: list[str] = []
    baselines = layer1_payload.discipline_baselines
    if baselines.paddling and baselines.paddling.paddle_craft_types:
        crafts.extend(baselines.paddling.paddle_craft_types)
    if baselines.cycling and baselines.cycling.bike_types_available:
        crafts.extend(baselines.cycling.bike_types_available)
    return sorted(set(crafts))


def _athlete_discipline_overrides(layer1_payload: Layer1Payload) -> dict[str, dict]:
    """X2 — unpack the athlete's discipline weighting into Layer 2A's
    `athlete_discipline_overrides` shape (`{discipline_id: {"weight": pct}}`,
    consumed by `_compute_load_weight` per spec §5.4). `discipline_slug` stores
    the canonical `discipline_id` (X2 write convention), so this is a direct
    remap. Empty weighting → `{}` and 2A falls back to race-time-midpoint
    system defaults."""
    return {
        r.discipline_slug: {"weight": float(r.weight_pct)}
        for r in layer1_payload.training_history.discipline_weighting
    }


def _derive_race_discipline_mix(
    target_race_event: RaceEventPayload | None,
) -> dict[str, float]:
    """X3 — derive the race's per-discipline weight signal from its terrain
    breakdown into Layer 2A's `race_discipline_overrides` shape
    (`{discipline_id: pct}`), consumed at the top of the pooling precedence
    chain (race > athlete > bridge, `_apply_modality_group_pooling`).

    Group-sums `pct_of_race` over the terrain rows that carry a
    `discipline_id`. Race-wide rows (`discipline_id is None`,
    Modality_Group_Spec §10) are dropped — they apportion across every
    included discipline, not one, so they hold no per-discipline signal.
    Percentage sums pass through unnormalized: the downstream
    `_normalize_load_weights` pass rescales the included set to sum 1.0.
    Empty (no event, or no discipline-tagged terrain) → `{}`, leaving the
    override inert (2A falls back to athlete, then bridge midpoints).

    The same `{discipline_id: pct}` map is the shared seam for #509's
    inclusion axis (a discipline with a race weight → `included`); kept a
    standalone helper so that slice reads it off the keys without rework."""
    if target_race_event is None:
        return {}
    mix: dict[str, float] = {}
    for entry in target_race_event.race_terrain:
        if entry.discipline_id is None:
            continue
        mix[entry.discipline_id] = mix.get(entry.discipline_id, 0.0) + float(
            entry.pct_of_race
        )
    return mix


def _q_modality_groups(db: Any) -> dict[str, list[str]]:
    """X1b.3b — `{discipline_id: [group_id, ...]}` from
    `layer0.discipline_modality_membership` (active rows). Mirrors
    `layer2a/builder.py:_load_modality_groups` (the third consumer — promote to
    a shared reader on a fourth). Empty dict → substitution narrowing is off."""
    cur = db.execute(
        "SELECT discipline_id, group_id "
        "FROM layer0.discipline_modality_membership "
        "WHERE superseded_at IS NULL"
    )
    out: dict[str, list[str]] = {}
    for row in cur.fetchall():
        out.setdefault(row["discipline_id"], []).append(row["group_id"])
    return out


def _q_craft_discipline_aliases(db: Any) -> dict[str, list[str]]:
    """X1b.3b — `{craft_name: [discipline_id, ...]}` (many-to-many) from
    `layer0.craft_discipline_aliases` (active rows). Empty dict → substitution
    narrowing is off (pre-X1b.3b behavior)."""
    cur = db.execute(
        "SELECT craft_name, discipline_id "
        "FROM layer0.craft_discipline_aliases "
        "WHERE superseded_at IS NULL"
    )
    out: dict[str, list[str]] = {}
    for row in cur.fetchall():
        out.setdefault(row["craft_name"], []).append(row["discipline_id"])
    return out


def _q_modality_group_kind(db: Any) -> dict[str, str]:
    """#540 slice 2c.2c — `{group_id: group_kind}` from `layer0.modality_groups`
    (active rows). The craft axis reads it to find a discipline's `group_kind`
    (bike/paddle = craft-bearing). Empty dict → the craft axis is inert (every
    discipline passes straight to the terrain axis)."""
    cur = db.execute(
        "SELECT group_id, group_kind FROM layer0.modality_groups "
        "WHERE superseded_at IS NULL"
    )
    return {row["group_id"]: row["group_kind"] for row in cur.fetchall()}


def _q_craft_group_kind(db: Any) -> dict[str, str]:
    """#540 slice 2c.2c — `{craft_name: group_kind}` from
    `layer0.craft_discipline_aliases` (active rows; `group_kind` is per-craft,
    constant across its discipline rows). Pairs with `_q_craft_discipline_aliases`
    to drive the craft axis. Empty dict → the craft axis is inert."""
    cur = db.execute(
        "SELECT DISTINCT craft_name, group_kind FROM layer0.craft_discipline_aliases "
        "WHERE superseded_at IS NULL"
    )
    return {row["craft_name"]: row["group_kind"] for row in cur.fetchall()}


def _q_craft_terrain_compatibility(db: Any) -> dict[str, set[str]]:
    """#586 WS-I — `{craft_name: {terrain_id, ...}}` (the terrains a craft can be
    ridden on) from `layer0.craft_terrain_compatibility` (active rows). Declared
    explicitly, not derived from the discipline graph (design §4), so the unified
    craft/terrain cascade can tell a road bike (no singletrack) from a gravel bike.
    Empty dict → the craft cascade's tiers 1–4 all miss (every craft discipline
    falls through to INDOOR/STRENGTH), so a missing table degrades, not crashes."""
    cur = db.execute(
        "SELECT craft_name, terrain_id FROM layer0.craft_terrain_compatibility "
        "WHERE superseded_at IS NULL"
    )
    out: dict[str, set[str]] = {}
    for row in cur.fetchall():
        out.setdefault(row["craft_name"], set()).add(row["terrain_id"])
    return out


def _q_terrain_gap_rules(db: Any) -> dict[str, list[tuple[str, float]]]:
    """#540 slice 2c.2 — `{target_terrain_id: [(proxy_terrain_id, fidelity), ...]}`
    from `layer0.terrain_gap_rules` (active rows with a proxy). Feeds the PROXY
    tier of `resolve_terrain_feasibility`. Mirrors `_q_modality_groups`. Empty
    dict → the PROXY tier is inert (cascade falls through to INDOOR/STRENGTH)."""
    cur = db.execute(
        "SELECT target_terrain_id, proxy_terrain_id, proxy_fidelity "
        "FROM layer0.terrain_gap_rules "
        "WHERE proxy_terrain_id IS NOT NULL AND superseded_at IS NULL"
    )
    out: dict[str, list[tuple[str, float]]] = {}
    for row in cur.fetchall():
        if row["proxy_fidelity"] is None:
            continue
        out.setdefault(row["target_terrain_id"], []).append(
            (row["proxy_terrain_id"], float(row["proxy_fidelity"]))
        )
    return out


def _q_terrain_names(db: Any) -> dict[str, str]:
    """`{terrain_id: canonical_name}` from `layer0.terrain_types` — maps TRN-xxx
    to the human surface name ('TRN-002' → 'Groomed Trail') for the deterministic
    venue menu in the feasibility line (#624). Empty dict → the menu falls back to
    the raw TRN id (degrades, doesn't crash)."""
    try:
        cur = db.execute(
            "SELECT terrain_id, canonical_name FROM layer0.terrain_types "
            "WHERE superseded_at IS NULL"
        )
        return {r["terrain_id"]: r["canonical_name"] for r in cur.fetchall()}
    except Exception:  # table unreachable → menu degrades to raw ids
        return {}


def _q_terrain_attributes(db: Any) -> dict[str, dict[str, bool]]:
    """`{terrain_id: {requires_elevation, technical_surface}}` from
    `layer0.terrain_types` — the surface attributes that derive a surface's
    training purpose for the #624 surface-specific routing (no new vocab; the
    columns already exist). Empty dict → routing no-ops and the feasibility line
    falls back to the flat venue menu (degrades, doesn't crash)."""
    try:
        cur = db.execute(
            "SELECT terrain_id, requires_elevation, technical_surface "
            "FROM layer0.terrain_types WHERE superseded_at IS NULL"
        )
        return {
            r["terrain_id"]: {
                "requires_elevation": bool(r["requires_elevation"]),
                "technical_surface": bool(r["technical_surface"]),
            }
            for r in cur.fetchall()
        }
    except Exception:  # table unreachable → routing degrades to the flat menu
        return {}


# Layer 2C `priority_per_discipline` rank — best (Critical) first. Drives the
# order of the strength-substitute exercise pool handed to the STRENGTH tier.
_PRIORITY_RANK: dict[str, int] = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass
class _FeasibilityInputs:
    """The environment-INDEPENDENT inputs to the feasibility cascade, gathered
    once per plan-gen. `_resolve_included_feasibility` runs the cascade against
    an injected `(locale_order, terrain_by_locale, equip_by_locale)` — the home
    cluster for the default plan, or an event window's reduced environment for a
    date-segment. Everything here (gap rules, craft maps, strength pools, the
    gated/included discipline sets) is identical across environments."""

    cluster: list[str]
    terrain_by_locale: dict[str, set[str]]
    equip_by_locale: dict[str, set[str]]
    gap_rules: dict[str, list[tuple[str, float]]]
    owned_crafts: list[str]
    craft_disciplines: dict[str, list[str]]
    craft_kind: dict[str, str]
    craft_terrain: dict[str, set[str]]
    discipline_groups: dict[str, list[str]]
    group_kind_by_group: dict[str, str]
    pool_by_discipline: dict[str, list[str]]
    gated: dict[str, str]
    included: list[Any]
    name_by_discipline: dict[str, str]
    # Deterministic venue display (#624 / #618-7): home-cluster locale → {name,
    # distance_km}, and terrain id → canonical name. Away segments rebuild meta
    # against the destination anchor; the subtractive segments reuse this.
    locale_meta: dict[str, dict[str, Any]]
    terrain_names: dict[str, str]
    # Surface attributes (#624) — terrain id → {requires_elevation,
    # technical_surface} — drive the per-purpose surface routing in
    # enrich_resolution_display. Read once with terrain_names.
    terrain_attrs: dict[str, dict[str, bool]]


def _gather_feasibility_inputs(
    db: Any, user_id: int, cone: "_UpstreamFullCone"
) -> "_FeasibilityInputs | None":
    """Read the cluster + all environment-independent cascade inputs once.
    Returns None (logging the reason) when the athlete has no resolvable home
    cluster — feasibility resolution is skipped entirely in that case."""
    cluster = locations.cluster_locale_ids(db, user_id)
    if not cluster:
        # Rule #15 observability: an empty cluster short-circuits the whole
        # cascade before the per-discipline log below, so log the reason here —
        # otherwise "no feasibility resolution" looks identical to "all feasible".
        print(
            f"_build_terrain_feasibility: user_id={user_id} cluster=[] "
            f"(no preferred/home locale, or home lacks coords) — "
            f"feasibility resolution skipped entirely"
        )
        return None
    terrain_by_locale = locations.cluster_terrain_by_locale(db, user_id, cluster)
    equip_by_locale = locations.cluster_equipment_by_locale(db, user_id, cluster)
    gap_rules = _q_terrain_gap_rules(db)
    locale_meta = locations.cluster_locale_meta(db, user_id, cluster)
    terrain_names = _q_terrain_names(db)
    terrain_attrs = _q_terrain_attributes(db)

    # Unified craft/terrain cascade (#586 WS-I) maps — craft disciplines walk
    # resolve_craft_terrain_feasibility; non-craft fall back to the terrain-only one.
    owned_crafts = _collect_athlete_crafts(cone.layer1_payload)
    craft_disciplines = _q_craft_discipline_aliases(db)
    craft_kind = _q_craft_group_kind(db)
    craft_terrain = _q_craft_terrain_compatibility(db)
    discipline_groups = _q_modality_groups(db)
    group_kind_by_group = _q_modality_group_kind(db)

    # The discipline's own mapped strength pool, ranked best-first by 2C
    # priority. tier 0 = unavailable at this locale set; keep 1/2/3.
    # #780 — the strength substitute pool reads the PRIMARY locale's 2C entry
    # (home-gym equipment; a home-substituted strength session is done at home),
    # while skill-gating dedupes across the FULL cluster (the same dict the
    # validator passes to `skill_gated_disciplines`). The primary entry is always
    # present (cluster[0] is the preferred locale; empty-cluster cones fall back
    # to {primary_locale}).
    primary_l2c = cone.layer2c_payloads[cone.primary_locale]
    pool_by_discipline: dict[str, list[str]] = {}
    for ex in primary_l2c.exercises_resolved:
        if ex.tier not in (1, 2, 3):
            continue
        for d_id in ex.discipline_ids:
            pool_by_discipline.setdefault(d_id, []).append(ex.exercise_id)
    # Rank each discipline's pool by its per-discipline priority (stable).
    for d_id, ids in pool_by_discipline.items():
        rank_of = {
            ex.exercise_id: _PRIORITY_RANK.get(
                ex.priority_per_discipline.get(d_id, ""), 99
            )
            for ex in primary_l2c.exercises_resolved
        }
        ids.sort(key=lambda e: rank_of.get(e, 99))

    gated = skill_gated_disciplines(cone.layer2c_payloads)
    included = [d for d in cone.layer2a_payload.disciplines if d.inclusion == "included"]
    name_by_discipline = {
        d.discipline_id: d.discipline_name for d in cone.layer2a_payload.disciplines
    }
    return _FeasibilityInputs(
        cluster=cluster,
        terrain_by_locale=terrain_by_locale,
        equip_by_locale=equip_by_locale,
        gap_rules=gap_rules,
        owned_crafts=owned_crafts,
        craft_disciplines=craft_disciplines,
        craft_kind=craft_kind,
        craft_terrain=craft_terrain,
        discipline_groups=discipline_groups,
        group_kind_by_group=group_kind_by_group,
        pool_by_discipline=pool_by_discipline,
        gated=gated,
        included=included,
        name_by_discipline=name_by_discipline,
        locale_meta=locale_meta,
        terrain_names=terrain_names,
        terrain_attrs=terrain_attrs,
    )


def _resolve_included_feasibility(
    fi: "_FeasibilityInputs",
    *,
    locale_order: list[str],
    terrain_by_locale: dict[str, set[str]],
    equip_by_locale: dict[str, set[str]],
    owned_crafts: list[str] | None = None,
    locale_meta: dict[str, dict[str, Any]] | None = None,
) -> dict[str, TerrainResolution]:
    """Run the existing EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE cascade for every
    included, non-skill-gated discipline against the supplied environment.

    The logic is identical for the home cluster and for an event window's
    reduced/replacement environment — only the inputs differ (Andy 2026-06-14: a
    window is just different terrain/equipment, not new resolution logic). Craft
    disciplines (bike/paddle) walk the unified craft/terrain cascade; it returns
    None for non-craft disciplines, which fall back to the terrain-only cascade.

    `owned_crafts=None` → the athlete's home crafts (`fi.owned_crafts`,
    byte-identical for the home cluster + the subtractive Slice-1 segments). An
    `away` segment passes `[]` (Slice 2, F4 — home crafts don't travel; the
    SAME cascade runs, the craft tiers just find nothing and the walk degrades
    through INDOOR→STRENGTH→REALLOCATE). Slice 4 supplies declared brought-craft."""
    crafts = fi.owned_crafts if owned_crafts is None else owned_crafts
    meta = fi.locale_meta if locale_meta is None else locale_meta
    out: dict[str, TerrainResolution] = {}
    for d in fi.included:
        if d.discipline_id in fi.gated:
            continue
        resolution = resolve_craft_terrain_feasibility(
            d.discipline_id,
            owned_crafts=crafts,
            craft_disciplines=fi.craft_disciplines,
            craft_group_kind=fi.craft_kind,
            discipline_groups=fi.discipline_groups,
            group_kind=fi.group_kind_by_group,
            craft_terrain=fi.craft_terrain,
            locale_order=locale_order,
            cluster_terrain_by_locale=terrain_by_locale,
            cluster_equipment_by_locale=equip_by_locale,
            discipline_exercise_ids=fi.pool_by_discipline.get(d.discipline_id, []),
            discipline_names=fi.name_by_discipline,
        )
        if resolution is None:
            resolution = resolve_terrain_feasibility(
                d.discipline_id,
                locale_order=locale_order,
                cluster_terrain_by_locale=terrain_by_locale,
                cluster_equipment_by_locale=equip_by_locale,
                gap_rules=fi.gap_rules,
                discipline_exercise_ids=fi.pool_by_discipline.get(d.discipline_id, []),
            )
        if resolution is not None:
            # Deterministic venue display (#624 / #618-7): attach the saved-locale
            # NAME + distance (and, for EXACT, the per-terrain nearest-venue menu)
            # so the synthesis line cites real locales instead of leaking a slug or
            # inventing a venue.
            out[d.discipline_id] = enrich_resolution_display(
                resolution,
                locale_order=locale_order,
                locale_meta=meta,
                terrain_names=fi.terrain_names,
                terrain_by_locale=terrain_by_locale,
                terrain_attrs=fi.terrain_attrs,
                craft_terrain=fi.craft_terrain,
            )
    return out


def _build_terrain_feasibility(
    db: Any,
    user_id: int,
    cone: "_UpstreamFullCone",
) -> dict[str, TerrainResolution]:
    """#540 slice 2c.2 — resolve, per included discipline, where/how its sessions
    can actually be done across the athlete's locale cluster (terrain axis).

    Runs the deterministic EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE cascade
    (`resolve_terrain_feasibility`) on existing layer0 data — the cluster
    terrain/equipment maps, `terrain_gap_rules`, and the discipline's own 2C
    mapped exercises. Skill-gated disciplines (#336) are EXCLUDED: they are
    already substituted to strength at the session level by the skill-capability
    gate, so running the terrain cascade on them would emit a conflicting
    directive (the two compose by partition, not by clobber). Unconstrained
    disciplines (resolver returns None) are dropped — nothing to guide.

    Resolves the DEFAULT home cluster. Event-window date-segments resolve the
    same cascade against a reduced environment via `_build_event_window_overlay`
    (Event Windows Slice 1)."""
    fi = _gather_feasibility_inputs(db, user_id, cone)
    if fi is None:
        return {}
    out = _resolve_included_feasibility(
        fi,
        locale_order=fi.cluster,
        terrain_by_locale=fi.terrain_by_locale,
        equip_by_locale=fi.equip_by_locale,
    )

    # Bind the gathered inputs to the local names the detailed Rule #15 log below
    # was written against (kept verbatim from the pre-refactor function).
    cluster = fi.cluster
    terrain_by_locale = fi.terrain_by_locale
    equip_by_locale = fi.equip_by_locale
    owned_crafts = fi.owned_crafts
    craft_terrain = fi.craft_terrain
    craft_kind = fi.craft_kind
    discipline_groups = fi.discipline_groups
    group_kind_by_group = fi.group_kind_by_group
    gated = fi.gated
    included = fi.included
    name_by_discipline = fi.name_by_discipline
    pool_by_discipline = fi.pool_by_discipline
    gap_rules = fi.gap_rules

    # Rule #15 observability: the cascade was print()-silent, so a plan
    # over-saturated with strength substitutions couldn't be traced to its
    # cause. Log, per discipline, WHY each tier resolved as it did — required
    # vs. available terrain, the owned/proxy crafts + which of their compatible
    # terrains are in-cluster (the craft cascade's tiers 1–4), gap-rule proxies
    # (the non-craft PROXY tier), indoor machines + whether they're in the
    # equipment pool (INDOOR), strength-pool size (STRENGTH) — plus the
    # skill-gate toggle and craft status. A STRENGTH/reallocate outcome is then
    # attributable to a real gap vs. a mis-read/empty terrain/equipment input
    # ("the substitute should have been in the cluster"). (pv=69 triage.)
    _incl_dbg = {d.discipline_id: d.inclusion for d in cone.layer2a_payload.disciplines}
    print(f"_build_terrain_feasibility: user_id={user_id} 2A_inclusion={_incl_dbg}")
    _terr_by_loc = {loc: sorted(terrain_by_locale.get(loc, set())) for loc in cluster}
    _equip_by_loc = {loc: sorted(equip_by_locale.get(loc, set())) for loc in cluster}
    _cluster_terr = set().union(*terrain_by_locale.values()) if terrain_by_locale else set()
    _cluster_equip = set().union(*equip_by_locale.values()) if equip_by_locale else set()
    print(
        f"_build_terrain_feasibility: user_id={user_id} cluster={cluster} "
        f"terrain_by_locale={_terr_by_loc} equipment_by_locale={_equip_by_loc} "
        f"owned_crafts={sorted(owned_crafts) if owned_crafts else []} "
        f"craft_terrain={ {c: sorted(t) for c, t in sorted(craft_terrain.items())} } "
        f"skill_gated={dict(sorted(gated.items()))}"
    )

    def _craft_kind_of(disc_id: str) -> str | None:
        for g in discipline_groups.get(disc_id, []):
            k = group_kind_by_group.get(g)
            if k in ("bike", "paddle"):
                return k
        return None

    for d in included:
        d_id = d.discipline_id
        d_name = name_by_discipline.get(d_id, "?")
        if d_id in gated:
            print(
                f"  feasibility[{d_id}/{d_name}]: SKILL-GATED "
                f"toggle='{gated[d_id]}' OFF — excluded from terrain cascade, "
                f"strength-substituted at the session level (#336)"
            )
            continue
        req = sorted(required_terrains(d_id))
        if not req:
            print(
                f"  feasibility[{d_id}/{d_name}]: unconstrained "
                f"(no terrain requirement) — scheduled as-is"
            )
            continue
        machines = list(indoor_machines(d_id))
        res = out.get(d_id)
        tier = res.tier if res is not None else "DROPPED"
        craft = (
            f" craft_tier={res.craft_tier} owned_craft={res.owned_craft}"
            if res is not None and res.craft_tier
            else ""
        )
        kind = _craft_kind_of(d_id)
        if kind is not None:
            # Craft discipline — log the crafts and the terrains they can ride.
            same_kind = [c for c in sorted(set(owned_crafts)) if craft_kind.get(c) == kind]
            rideable = {
                c: sorted((craft_terrain.get(c, set()) & _cluster_terr)) for c in same_kind
            }
            detail = (
                f"craft_kind={kind} owned_same_kind={same_kind} "
                f"craft_rideable_in_cluster={rideable}"
            )
        else:
            proxies = sorted({(p, round(f, 2)) for r in req for p, f in gap_rules.get(r, [])})
            detail = (
                f"proxies={proxies} "
                f"proxy_in_cluster={[p for p, _f in proxies if p in _cluster_terr]}"
            )
        print(
            f"  feasibility[{d_id}/{d_name}]: tier={tier}{craft} "
            f"required_terrain={req} "
            f"exact_match={sorted(set(req) & _cluster_terr)} "
            f"{detail} "
            f"indoor_machines={machines} "
            f"machine_in_cluster={[m for m in machines if m in _cluster_equip]} "
            f"strength_pool_n={len(pool_by_discipline.get(d_id, []))}"
        )
    return out


def _reduced_env(
    fi: "_FeasibilityInputs", overrides: tuple[EventWindowOverride, ...]
) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    """Apply a date-segment's active SUBTRACTIVE overrides to the home cluster →
    `(locale_order, terrain_by_locale, equip_by_locale)` for the reduced
    environment. `indoor_only` removes all outdoor terrain (outdoor cardio
    reroutes to the indoor machine / strength — equipment is untouched);
    `locale_unavailable(L)` drops locale L entirely from terrain + equipment +
    the locale order. Overlapping overrides apply cumulatively (union of
    subtractions per spec §8). A locale not in the cluster is a no-op."""
    locale_order = list(fi.cluster)
    terrain = {loc: set(s) for loc, s in fi.terrain_by_locale.items()}
    equip = {loc: set(s) for loc, s in fi.equip_by_locale.items()}
    for ov in overrides:
        if ov.override_type == "indoor_only":
            terrain = {loc: set() for loc in terrain}
        elif ov.override_type == "locale_unavailable" and ov.unavailable_locale:
            loc = ov.unavailable_locale
            terrain.pop(loc, None)
            equip.pop(loc, None)
            locale_order = [x for x in locale_order if x != loc]
    return locale_order, terrain, equip


def _build_event_window_overlay(
    db: Any,
    user_id: int,
    cone: "_UpstreamFullCone",
    *,
    plan_start: date,
    plan_end: date,
    home_feasibility: dict[str, TerrainResolution],
) -> tuple[list[EventWindowSegment], list[Any]]:
    """Event Windows Slice 1 (#581 WS-H) — date-segment the plan span by the
    athlete's declared event windows and resolve the EXISTING cascade once per
    reduced environment. Returns `(segments, overlapping_windows)`:

      - `segments` — the atomic date sub-ranges whose routing DIFFERS from home,
        each carrying only the changed disciplines (the synthesis overlay
        payload rendered date-scoped by `per_phase`).
      - `overlapping_windows` — the declared windows overlapping the span, fed to
        `compute_event_windows_hash` for the plan cache key.

    Counts stay on the home environment (spec §4): this only re-scopes the
    per-date feasibility synthesis composes against, never the grid / E2 cap."""
    windows = load_event_windows(db, user_id)
    overlapping = [
        w for w in windows if w.end_date >= plan_start and w.start_date <= plan_end
    ]
    if not overlapping:
        return [], []
    fi = _gather_feasibility_inputs(db, user_id, cone)
    if fi is None:
        # No resolvable home cluster — windows can't subtract from an empty env.
        # Still surface the overlapping windows so the cache key reflects them.
        print(
            f"event_window_overlay: user_id={user_id} {len(overlapping)} window(s) "
            f"overlap the plan span but cluster=[] — no reduced-env resolution"
        )
        return [], overlapping

    # Slice 4 (#581 WS-H) — the standing craft↔locale map, loaded once. The away
    # branch unions the crafts kept at any locale in the destination cluster (b)
    # with the window's brought-craft (c) → the away segment's owned_crafts.
    craft_locale_map = load_craft_locales(db, user_id)
    raw = [
        (
            w.start_date,
            w.end_date,
            EventWindowOverride(
                w.override_type,
                w.unavailable_locale,
                w.away_locale,
                brought_craft=tuple(w.brought_craft),
            ),
        )
        for w in overlapping
    ]
    segments: list[EventWindowSegment] = []
    for seg_start, seg_end, active in segment_window_boundaries(plan_start, plan_end, raw):
        away_ov = next((ov for ov in active if ov.override_type == "away"), None)
        away_feasibility: dict[str, TerrainResolution] | None = None
        assumed_baseline: str | None = None
        _away_dbg = ""
        if away_ov is not None and away_ov.away_locale:
            # REPLACEMENT env (Slice 2): `away` wins over any co-active subtractive
            # override on the same dates (you can't be home-indoor-only AND away).
            # The destination's OWN radius cluster — re-anchored cluster_locale_ids,
            # the same logic as home (Andy 2026-06-14). Home crafts don't travel:
            # owned_crafts=[] (F4 — the SAME cascade runs, the craft tiers just
            # find nothing and the walk degrades through INDOOR→STRENGTH→REALLOCATE).
            away_cluster = locations.cluster_locale_ids(
                db, user_id, anchor_locale=away_ov.away_locale
            )
            # Slice 4 (#581 WS-H): away craft = brought-craft on this window (c) ∪
            # standing craft kept at any locale in the destination cluster (b).
            # Empty union → byte-identical to the Slice-2a owned_crafts=[] path.
            brought = set(away_ov.brought_craft)
            standing = {
                c for loc in away_cluster for c in craft_locale_map.get(loc, ())
            }
            away_crafts = sorted(brought | standing)
            reduced = _resolve_included_feasibility(
                fi,
                locale_order=away_cluster,
                terrain_by_locale=locations.cluster_terrain_by_locale(
                    db, user_id, away_cluster
                ),
                equip_by_locale=locations.cluster_equipment_by_locale(
                    db, user_id, away_cluster
                ),
                owned_crafts=away_crafts,
                # Re-anchor venue display at the destination (its own distances).
                locale_meta=locations.cluster_locale_meta(
                    db, user_id, away_cluster, anchor_locale=away_ov.away_locale
                ),
            )
            away_feasibility = reduced
            # Slice 3 (F8): if the destination is cold (no logged equipment/
            # terrain) and its category has a baseline, the away cluster resolved
            # above ran on that ASSUMED baseline — mark the segment so the overlay
            # tells the athlete to log actuals on arrival (Trigger-#1 wording).
            assumed_baseline = locations.locale_assumed_baseline_display(
                db, user_id, away_ov.away_locale
            )
            # Rule #15 (spec §7): the away env + the resolved craft set with its
            # provenance — the #1 reason an away bike/paddle day lands on strength
            # is "no craft available", so print the inputs that drove the decision
            # (brought on the window (c) vs kept at the destination (b)).
            _away_dbg = (
                f" away_locale={away_ov.away_locale} away_cluster={away_cluster} "
                f"owned_crafts={away_crafts} (brought={sorted(brought)} "
                f"standing={sorted(standing)}) assumed_baseline={assumed_baseline}"
            )
        else:
            locale_order, terrain, equip = _reduced_env(fi, active)
            reduced = _resolve_included_feasibility(
                fi,
                locale_order=locale_order,
                terrain_by_locale=terrain,
                equip_by_locale=equip,
            )
        changed = {d: r for d, r in reduced.items() if home_feasibility.get(d) != r}
        # Rule #15 (spec §7): name, per discipline, the tier the cascade landed
        # on for this segment — so a surprising windowed-day plan is diagnosable
        # from logs alone (never assuming indoor/strength).
        _ov = ",".join(
            ov.override_type
            + (f":{ov.unavailable_locale}" if ov.unavailable_locale else "")
            + (f":{ov.away_locale}" if ov.away_locale else "")
            for ov in active
        )
        print(
            f"event_window_overlay: user_id={user_id} "
            f"dates={seg_start.isoformat()}..{seg_end.isoformat()} override={_ov}"
            f"{_away_dbg} "
            f"tiers={ {d: r.tier for d, r in sorted(changed.items())} }"
            + ("" if changed else " (no routing change — segment not emitted)")
        )
        if changed:
            segments.append(
                EventWindowSegment(
                    seg_start, seg_end, active, changed,
                    away_feasibility=away_feasibility,
                    assumed_baseline_category=assumed_baseline,
                )
            )
    return segments, overlapping


def _upstream_full_cone(
    db: Any,
    user_id: int,
    today: date,
    *,
    cache: Layer4Cache,
    target_race_event: RaceEventPayload | None,
    viability_current_date: date | None = None,
) -> _UpstreamFullCone:
    """Compose the full upstream cone (Layer 1 → 2A → 2B → 2D → 2C → 3A →
    3B → 2E) shared by race_week_brief + plan_refresh + plan_create.

    Pipeline ordering note: Layer 2E runs after Layer 3B because it
    consumes `start_phase` from 3B's `periodization_shape`. `primary_locale`
    + `locale_terrain_ids` are read before Layer 2B (terrain pipeline);
    `locale_equipment_pool` is read before Layer 2C.

    `cache` threads through to the Layer 3A + 3B cached wrappers
    (`cache.backend` exposes the shared `layer4_cache` storage). The
    wrappers compose per-spec cache keys + handle hit/miss directly; the
    Layer 4 per-entry-point wrapper still wraps the whole pipeline so a
    Layer-4 cache hit short-circuits 3A/3B entirely.

    Pre-flight gates raised here (3, shared across all 3 consumers):
    `etl_version_set_undiscoverable`, `framework_sport_missing`,
    `primary_locale_missing`.

    `target_race_event=None` is supported for the no-event-mode plan_refresh
    path: Layer 2B's `race_terrain` becomes `[]` (loosened per Phase 5.1
    form-refresh C), Layer 2E's `target_events` becomes `[]`, and Layer 3B's
    `race_event_payload` becomes `None`. The orchestrator never raises
    `no_target_event` here — that gate belongs to entry points that
    require a race (race_week_brief inlines it before calling the helper).
    """
    etl_version_set = _q_current_etl_version_set(db)
    as_of = datetime.combine(today, time.min)

    layer1_payload = build_layer1_payload(db, user_id)
    # D-73 Phase 5.2 Bucket E.(b) — race-row override takes precedence over
    # athlete-profile primary_sport. When set on the target race, Layer 2A
    # classifies for the race's own sport (e.g. trail runner doing one AR
    # race) without churning the athlete's profile. Falls back to
    # primary_sport when the override is unset OR no target race exists.
    framework_sport = (
        target_race_event.framework_sport if target_race_event is not None else None
    )
    if not framework_sport:
        framework_sport = layer1_payload.identity.primary_sport
    if not framework_sport:
        raise OrchestrationError(
            "framework_sport_missing",
            f"layer1.identity.primary_sport is empty for user_id={user_id}",
        )

    # D-73 Phase 5.2 Bucket E.(b)-B2 — race-row `included_discipline_ids`
    # narrows the bridge-derived discipline list when supplied. Layer 2A
    # post-filters and the rest of the cone (2B/2C/2D/3A/3B) reads the
    # narrowed list naturally via `included_discipline_ids` below. The
    # route layer auto-clears `included_discipline_ids` on framework_sport
    # change so the filter never references stale IDs.
    discipline_id_filter = (
        target_race_event.included_discipline_ids
        if target_race_event is not None
        else None
    )
    layer2a_payload = q_layer2a_discipline_classifier_payload(
        db,
        framework_sport=framework_sport,
        discipline_id_filter=discipline_id_filter,
        etl_version_set=etl_version_set,
        athlete_discipline_overrides=_athlete_discipline_overrides(layer1_payload),
        # X4 — race terrain mix wins over the athlete split, which wins over
        # bridge midpoints (precedence resolved in _apply_modality_group_pooling).
        # Inert when the race carries no discipline-tagged terrain.
        race_discipline_overrides=_derive_race_discipline_mix(target_race_event),
    )
    included_discipline_ids = [
        d.discipline_id
        for d in layer2a_payload.disciplines
        if d.inclusion == "included"
    ]

    primary_locale = _q_primary_locale(db, user_id)
    locale_terrain_ids = _q_locale_terrain_ids(db, user_id, primary_locale)

    layer2b_payload = q_layer2b_terrain_classifier_payload(
        db,
        race_terrain=(
            target_race_event.race_terrain if target_race_event is not None else []
        ),
        locale_terrain_ids=locale_terrain_ids,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
        # D-73 Phase 5.2 Bucket C (l) — thread athlete skill-capability
        # state into 2B so `requires_skill_capability` flags can fire
        # for terrains the athlete hasn't acquired the matching skill
        # for. Capture surface deferred; default state is the empty
        # dict (every toggle OFF), mirroring the gear-toggle precedent.
        skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
    )

    layer2d_payload = q_layer2d_injury_risk_profile_payload(
        db,
        injuries=layer1_payload.health_status.current_injuries,
        conditions=layer1_payload.health_status.health_conditions_active,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
        today=today,
    )

    cluster = locations.cluster_locale_ids(db, user_id)
    # #780 — invoke Layer 2C once per cluster locale, each resolved against THAT
    # locale's own effective equipment (was: a single call for the primary locale
    # carrying the cluster-UNION pool — the documented "today stubbed to
    # [primary_locale]" stub). The per-locale dict is what the validator's cluster
    # check (rule 6c) and the locale-assign candidate set read, so a session
    # correctly placed at a nearby venue (e.g. groomed trail at Cleburne) is no
    # longer rejected as "not in cluster" and nearby venues enter the candidate
    # set. Each payload's hash folds into the Layer-4 cache key via
    # compute_layer2c_bundle_hash, so adding/removing a saved locale invalidates
    # cached blocks (single-locale clusters stay byte-identical). Empty cluster (no
    # resolvable home) falls back to the primary locale alone, preserving the
    # primary entry that the strength pool + skill-gate read.
    cluster_for_2c = cluster or [primary_locale]
    layer2c_payloads = {
        locale: q_layer2c_equipment_mapper_payload(
            db,
            locale_id=locale,
            locale_equipment_pool=sorted(
                locations.locale_effective_tags(db, user_id, locale)
            ),
            cluster_locale_ids=cluster_for_2c,
            cluster_gear_toggle_states={},
            included_discipline_ids=included_discipline_ids,
            layer2d_payload=layer2d_payload,
            etl_version_set=etl_version_set,
            # D-73 Phase 5.2 Bucket C (l) — mirror of the 2B wire above.
            skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
        )
        for locale in cluster_for_2c
    }
    # Rule #15 — trace the per-locale 2C fan-out: which locales got a payload and
    # each one's effective-pool size. A starved cluster (single locale, or a
    # nearby locale resolving an empty pool) is then attributable here rather than
    # surfacing downstream as a mystery "session not in cluster" / no-venue plan.
    print(
        f"_upstream_full_cone: user_id={user_id} layer2c built per-locale for "
        f"cluster={cluster_for_2c} pool_sizes="
        f"{ {loc: len(p.effective_pool) for loc, p in layer2c_payloads.items()} }"
    )

    integration_bundle = assemble_layer3a_integration_bundle(db, user_id, as_of)
    layer3a_payload = llm_layer3a_athlete_state_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
    )

    # 3B reasons about goal/timeline viability, so its `current_date` anchors
    # the training timeline. plan_create passes the (possibly future)
    # `plan_start_date` via `viability_current_date` so 3B's
    # `time_to_event_weeks` is measured from when training actually begins —
    # matching Layer 4's `_validate_plan_create_inputs` check
    # `(event_date - plan_start_date) // 7`. race_week_brief / plan_refresh
    # leave it None and anchor on `today`. 3A's `as_of` + 2E stay on `today`
    # (athlete state + nutrition baseline are "now", not the plan start).
    # §H.2 goal context (2026-05-26) — thread the athlete's captured goal
    # fields off the target race row into Layer 3B's event-mode goal block +
    # HITL triggers (3B.first_time_competitive_goal). Closes the deployed-shape
    # gap: 3B previously saw only the cached wrapper's hardcoded
    # goal_outcome="Finish". `race_duration_hr` / `race_terrain` are already on
    # the payload (so the cache key already varies on them) but never reached
    # 3B's prompt — the builder reads them from kwargs — so thread them too.
    # `race_distance_km` is left out: the builder already falls back to
    # `RaceEventPayload.distance_km`. `previous_attempts` (Slice 2) threads as
    # plain dicts the builder consumes via `.get("outcome")` / `.get("dnf_cause")`
    # — it unblocks the `3B.dnf_recurrence_risk` HITL flag. All None / empty in
    # no-event mode (the cached wrapper then falls back to the conservative
    # "Finish" tier for legacy / uncaptured rows).
    section_h2_kwargs: dict[str, Any] = {}
    if target_race_event is not None:
        section_h2_kwargs = {
            "goal_outcome": target_race_event.goal_outcome,
            "first_time_at_distance": target_race_event.first_time_at_distance,
            "time_goal": target_race_event.time_goal,
            "race_pack_weight_kg": (
                float(target_race_event.race_pack_weight_kg)
                if target_race_event.race_pack_weight_kg is not None
                else None
            ),
            "race_duration_hr": (
                float(target_race_event.estimated_duration_hr)
                if target_race_event.estimated_duration_hr is not None
                else None
            ),
            "race_terrain": (
                [e.terrain_id for e in target_race_event.race_terrain] or None
            ),
            "previous_attempts": (
                [
                    {"outcome": a.outcome, "dnf_cause": a.dnf_cause or ""}
                    for a in target_race_event.previous_attempts
                ]
                or None
            ),
        }
    layer3b_payload = llm_layer3b_goal_timeline_viability_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        race_event_payload=target_race_event,
        current_date=(
            viability_current_date if viability_current_date is not None else today
        ),
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
        **section_h2_kwargs,
    )

    target_events: list[Layer2ETargetEvent] = []
    if target_race_event is not None:
        target_events.append(
            Layer2ETargetEvent(
                event_id=str(target_race_event.race_event_id),
                event_name=target_race_event.name,
                event_date=target_race_event.event_date,
                framework_sport=framework_sport,
                estimated_duration_hr=(
                    float(target_race_event.estimated_duration_hr)
                    if target_race_event.estimated_duration_hr is not None
                    else _DURATION_HR_BY_RACE_FORMAT.get(
                        target_race_event.race_format, 8.0
                    )
                ),
            )
        )
    included_disciplines = [
        d for d in layer2a_payload.disciplines if d.inclusion == "included"
    ]
    layer2e_payload = q_layer2e_nutrition_baseline_payload(
        db,
        identity=layer1_payload.identity,
        health_status=layer1_payload.health_status,
        performance=layer1_payload.performance,
        target_events=target_events,
        lifestyle=layer1_payload.lifestyle,
        included_disciplines=included_disciplines,
        framework_sport=framework_sport,
        current_phase=layer3b_payload.periodization_shape.start_phase,
        etl_version_set=etl_version_set,
        athlete_id=str(user_id),
        today=today,
    )

    # Best-fit re-model — training-substitution resolver. Consumes the Layer 2B
    # per-discipline terrain blocks (no extra SQL) + the athlete's owned crafts
    # (handed verbatim; the LLM picks — gate Q2). Pure Python; safe to run
    # unconditionally (empty terrain → empty recommendations).
    training_substitution_payload = resolve_training_substitution(
        terrain_by_discipline=layer2b_payload.terrain_by_discipline,
        athlete_crafts=_collect_athlete_crafts(layer1_payload),
        etl_version_set=etl_version_set,
        discipline_names={
            d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines
        },
        # X1b.3b — narrow craft candidates to the race discipline's modality
        # group(s). Loaded once at cone construction (1 query each).
        discipline_modality_groups=_q_modality_groups(db),
        craft_discipline_aliases=_q_craft_discipline_aliases(db),
    )

    return _UpstreamFullCone(
        etl_version_set=etl_version_set,
        framework_sport=framework_sport,
        primary_locale=primary_locale,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        layer2b_payload=layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=layer2d_payload,
        layer2e_payload=layer2e_payload,
        training_substitution_payload=training_substitution_payload,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
    )


def _apply_locale_assign(
    db: Any,
    user_id: int,
    payload: Layer4Payload,
    layer2c_payloads: dict[str, "Layer2CPayload"],
) -> Layer4Payload:
    """Track 2 slice 2c — run the deterministic post-synthesis locale-assign
    pipeline (`layer4/locale_assign.py`) on the synthesized payload, swap the
    payload's sessions for the assigned-and-substituted set. Cardio + rest
    sessions are untouched (cardio routing deferred to slice 2c.2).

    Runs OUTSIDE the cached engine — locale-only edits already invalidate
    Layer 2C and transitively Layer 4 (Track 1 eviction policy), so this
    is a pure post-hydrate transform. Failure here is non-fatal: a degraded
    pass-through preserves the original payload + logs the cause, so a
    locale-assign defect can never wedge plan generation.
    """
    try:
        new_sessions, _diag = assign_locales(
            sessions=list(payload.sessions),
            layer2c_payloads=layer2c_payloads,
            db=db,
            user_id=user_id,
            llm_substitute_caller=None,  # in-flight wiring; deterministic ladder ships first
        )
        return payload.model_copy(update={"sessions": new_sessions})
    except Exception as exc:  # noqa: BLE001 — see docstring on the degraded path
        import logging
        logging.getLogger(__name__).warning(
            "_apply_locale_assign: degraded pass-through after exception: %s", exc,
        )
        return payload


def _apply_rx_wire(
    db: Any,
    user_id: int,
    payload: Layer4Payload,
    layer2c_payloads: dict[str, "Layer2CPayload"],
) -> Layer4Payload:
    """Track 2 slice 2d — run the deterministic post-synth rx wiring
    (`layer4/rx_wire.py`) on the synthesized payload. For each strength
    exercise: overwrite `load_prescription` with the precise `current_rx`
    baseline when one exists; else write a category-keyed RPE template and
    append `first_exposure` to `coaching_flags`. NO LLM in this path.

    Runs AFTER `_apply_locale_assign` on the same hydrated payload (per
    spec §10 slice-2d row): substitutions decided by the locale-assign step
    can change which exercise we look up rx for, so rx wiring must see the
    post-substitution exercise list. `current_rx` reads are per-athlete
    state, intentionally outside the block synthesis cache (a `current_rx`
    edit updates the rendered prescription on next read without
    invalidating Layer 4 blocks — spec §9).

    Degraded pass-through on exception: an rx-wire defect can never wedge
    plan generation.
    """
    try:
        new_payload, _diag = apply_current_rx(
            payload, db, user_id, layer2c_payloads,
        )
        return new_payload
    except Exception as exc:  # noqa: BLE001 — see docstring on the degraded path
        import logging
        logging.getLogger(__name__).warning(
            "_apply_rx_wire: degraded pass-through after exception: %s", exc,
        )
        return payload


def orchestrate_race_week_brief(
    db: Any,
    user_id: int,
    *,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end race_week_brief pipeline for `user_id`.

    Algorithm:
    1. Load target race event; raise `OrchestrationError('no_target_event')`
       when the athlete has no `is_target_event=true` race row.
    2. Pre-flight auto-fire gate: raise
       `OrchestrationError('race_week_brief_too_early')` when
       `days_to_event > 14`. This is a cheap optimization that saves the
       3A + 3B LLM calls on out-of-window invocations; `_validate_inputs`
       in `llm_layer4_race_week_brief` will also reject the same case.
    3. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_plan_refresh` per Phase 5.2 slice 2 D1 extract).
    4. Resolve the real prior Taper window + plan version from the athlete's
       active plan (#732 slice 1 — was two placeholders). The prior window is
       the currently-scheduled sessions over `[today, event_date]`: the
       athlete is ≤14 days out (gate above), so every session in that window
       is in the Taper phase by definition and is a candidate for the brief's
       `taper_session_overrides`. `plan_version_id` is the athlete's active
       plan version, the one the overrides are stamped with (and that #732
       slice 2 will persist them under). Raises
       `OrchestrationError('no_active_plan')` when the athlete has no active
       (`ready`, non-archived) plan version — the brief has nothing to
       attach its overrides to.
    5. Compose via `llm_layer4_race_week_brief_cached`.

    Failures from any upstream layer propagate verbatim; the orchestrator
    does not try/except them. Layer-3A / Layer-3B LLM failures surface as
    their respective driver errors; Layer 4 validator failures surface as
    `Layer4OutputError` or `Layer4InputError`.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    if race_event is None:
        raise OrchestrationError(
            "no_target_event",
            f"user_id={user_id} has no race_events row with is_target_event=true",
        )

    days_to_event = (race_event.event_date - today).days
    if days_to_event > _AUTO_FIRE_DAYS_TO_EVENT_MAX:
        raise OrchestrationError(
            "race_week_brief_too_early",
            f"days_to_event={days_to_event} > {_AUTO_FIRE_DAYS_TO_EVENT_MAX}",
        )

    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event
    )

    # #732 slice 1 — resolve the real prior Taper window + plan version
    # (was `prior_plan_session_window=[]` + `plan_version_id=1` placeholders).
    # Mirrors the caller-supplied inputs `orchestrate_plan_refresh` receives:
    # the brief MODIFIES the athlete's existing Taper sessions, so it needs
    # the real upcoming-session window and a real version to stamp/persist.
    # Lazy import: `plan_sessions_repo` imports `layer4.payload`, which pulls
    # in `layer4/__init__` -> this module; a top-level import here cycles when
    # `plan_sessions_repo` is imported first (e.g. via `routes/dashboard.py`).
    from plan_sessions_repo import (
        load_active_plan_version_id,
        load_scheduled_sessions_for_window,
    )

    plan_version_id = load_active_plan_version_id(db, user_id)
    if plan_version_id is None:
        raise OrchestrationError(
            "no_active_plan",
            f"user_id={user_id} has no active (ready, non-archived) plan version",
        )
    prior_plan_session_window = load_scheduled_sessions_for_window(
        db, user_id, start=today, end=race_event.event_date
    )

    return llm_layer4_race_week_brief_cached(
        user_id=user_id,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2a_payload=cone.layer2a_payload,
        layer2b_payload=cone.layer2b_payload,
        layer2c_payloads=cone.layer2c_payloads,
        layer2d_payload=cone.layer2d_payload,
        layer2e_payload=cone.layer2e_payload,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        race_event_payload=race_event,
        prior_plan_session_window=prior_plan_session_window,
        plan_version_id=plan_version_id,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        # Thread the training-substitution payload from the cone into the
        # brief's prompt body + cache key.
        training_substitution_payload=cone.training_substitution_payload,
        today=today,
    )


def orchestrate_single_session_synthesize(
    db: Any,
    user_id: int,
    request: SingleSessionRequest,
    suggestion_id: int,
    *,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end D-63 on-demand workout pipeline for `user_id`.

    Algorithm:
    1. Discover the active `etl_version_set` triplet from Layer 0.
    2. Build Layer 1.
    3. Call Layer 2A with `framework_sport=request.sport` — the athlete's
       per-request sport pick overrides their primary discipline mix
       (single-session is athlete-overriding behavior per D-63 §6.1; e.g.,
       Andy can pick Rowing for cross-training even though his primary
       sport is Adventure Racing). Layer2A's `Layer2AInputError` on an
       unknown framework_sport surfaces as
       `OrchestrationError('request_sport_unavailable')`.
    4. Compute `included_discipline_ids` from 2A; call Layer 2D.
    5. Locale branch (XOR per `SingleSessionRequest._check_locale_xor_quick_equipment`):
       - When `request.locale_slug` is non-None: validate the slug exists
         via `_q_locale_by_slug` (raise
         `OrchestrationError('locale_unknown')` on miss); read the locale's
         equipment pool; call Layer 2C against it; pass the resulting
         payload as `layer2c_payload_for_locale`.
       - When `request.locale_slug` is None ("Somewhere else"): skip Layer
         2C entirely; pass `layer2c_payload_for_locale=None`. The driver
         resolves equipment from `request.quick_equipment` directly per
         spec §3.3 row 4.
    6. Build the Layer 3A integration bundle + call
       `llm_layer3a_athlete_state_cached` (shares the Layer 4 cache backend
       via `cache.backend` per Phase 5.2 Layer 3 caching slice 2026-05-21 —
       same wrapper as the `_upstream_full_cone` call sites).
    7. Compose via `llm_layer4_single_session_synthesize_cached`.

    No `no_target_event` / `race_week_brief_too_early` gates — single-session
    is off-plan, off-race, and athlete-driven by definition. The driver's
    own `_validate_inputs` (`layer4/single_session.py` §4.4) covers
    locale-XOR-quick + 2C-payload-presence rules.

    Failures from any upstream layer propagate verbatim; the orchestrator
    does not try/except them (except for the targeted Layer2AInputError
    catch documented above).
    """
    if today is None:
        today = date.today()

    etl_version_set = _q_current_etl_version_set(db)
    as_of = datetime.combine(today, time.min)

    layer1_payload = build_layer1_payload(db, user_id)

    try:
        layer2a_payload = q_layer2a_discipline_classifier_payload(
            db,
            framework_sport=request.sport,
            etl_version_set=etl_version_set,
            athlete_discipline_overrides=_athlete_discipline_overrides(layer1_payload),
        )
    except Layer2AInputError as exc:
        raise OrchestrationError(
            "request_sport_unavailable",
            f"request.sport={request.sport!r} is not a known framework_sport: {exc}",
        ) from exc

    included_discipline_ids = [
        d.discipline_id
        for d in layer2a_payload.disciplines
        if d.inclusion == "included"
    ]

    layer2d_payload = q_layer2d_injury_risk_profile_payload(
        db,
        injuries=layer1_payload.health_status.current_injuries,
        conditions=layer1_payload.health_status.health_conditions_active,
        included_discipline_ids=included_discipline_ids,
        etl_version_set=etl_version_set,
        today=today,
    )

    layer2c_payload_for_locale = None
    if request.locale_slug is not None:
        if not _q_locale_by_slug(db, user_id, request.locale_slug):
            raise OrchestrationError(
                "locale_unknown",
                f"user_id={user_id} has no locale_profiles row with "
                f"locale={request.locale_slug!r}",
            )
        locale_equipment_pool = _q_locale_equipment_pool(
            db, user_id, request.locale_slug
        )
        layer2c_payload_for_locale = q_layer2c_equipment_mapper_payload(
            db,
            locale_id=request.locale_slug,
            locale_equipment_pool=locale_equipment_pool,
            cluster_locale_ids=[request.locale_slug],
            cluster_gear_toggle_states={},
            included_discipline_ids=included_discipline_ids,
            layer2d_payload=layer2d_payload,
            etl_version_set=etl_version_set,
            # D-73 Phase 5.2 Bucket C (l) — same wire as full-cone path.
            skill_toggle_states=layer1_payload.lifestyle.skill_toggle_states,
        )

    integration_bundle = assemble_layer3a_integration_bundle(db, user_id, as_of)
    layer3a_payload = llm_layer3a_athlete_state_cached(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2a_payload,
        integration_bundle=integration_bundle,
        as_of=as_of,
        etl_version_set=etl_version_set,
        cache_backend=cache.backend,
    )

    return llm_layer4_single_session_synthesize_cached(
        user_id=user_id,
        request=request,
        layer1_payload=layer1_payload.model_dump(mode="json"),
        layer2c_payload_for_locale=layer2c_payload_for_locale,
        layer2d_payload=layer2d_payload,
        layer3a_payload=layer3a_payload,
        suggestion_id=suggestion_id,
        etl_version_set=etl_version_set,
        cache=cache,
        session_date=today,
    )


def orchestrate_plan_refresh(
    db: Any,
    user_id: int,
    *,
    tier: Literal["T1", "T2", "T3"],
    refresh_scope_start: date,
    refresh_scope_end: date,
    plan_version_id: int,
    plan_version_id_parent: int,
    prior_plan_session_window: list[PlanSession],
    cache: Layer4Cache,
    parsed_intent: ParsedIntent | None = None,
    plan_start_date: date | None = None,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end D-64 plan-refresh pipeline for `user_id`.

    Algorithm:
    1. Load target race event (None OK — no-event-mode plans refresh fine
       without a target race; Layer 3B's `mode='no-event'` branch handles
       this downstream).
    2. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_race_week_brief` per Phase 5.2 slice 2 D1 extract).
    3. Pack the 5 Layer 2 payloads into a `Layer2Bundle` — D-64 driver
       expects the bundled input shape, not individual payloads (see
       `llm_layer4_plan_refresh` signature in `layer4/plan_refresh.py`).
    4. Compose via `llm_layer4_plan_refresh_cached`. The driver dispatches
       T1/T2/T3 internally; T3 cross-phase routes to Pattern A via
       `_route_t3_cross_phase_to_pattern_a` (shipped at Step 4f 2026-05-18).

    Pre-flight gates (3, all emitted by `_upstream_full_cone`):
    `etl_version_set_undiscoverable`, `primary_locale_missing`,
    `framework_sport_missing`. The orchestrator does NOT raise
    `no_target_event` (no-event refresh is supported) and does NOT pre-flight
    the auto-fire window (refresh fires on demand). `tier`/`refresh_scope_*`/
    `plan_version_id_parent`/`plan_start_date` validity is enforced by the
    driver's `_validate_inputs` per `Layer4_Spec.md` §4.3 — `Layer4InputError`
    propagates verbatim; the orchestrator does not wrap.

    `plan_version_id` + `plan_version_id_parent` + `prior_plan_session_window`
    + `parsed_intent` + `plan_start_date` are all caller-supplied kwargs
    pending the D-64 caller-side route + `plan_versions` table (matches the
    slice 1 D4 precedent for D-63's `suggestion_id`).

    `parsed_intent=None` is permitted — D-64 §5.4 documents graceful
    degradation when the NL parser is unavailable.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event
    )

    layer2_bundle = Layer2Bundle(
        a=cone.layer2a_payload,
        b=cone.layer2b_payload,
        c=cone.layer2c_payloads,
        d=cone.layer2d_payload,
        e=cone.layer2e_payload,
    )

    # #557 — mirror the create-side #540 terrain-feasibility cascade onto the
    # refresh path so a *refreshed* plan also never prescribes a session the
    # athlete can't physically do (e.g. climbing at a home with no climbing
    # terrain). Same deterministic builder + cone the create path uses; threaded
    # into the refresh prompt + folded into the plan_refresh cache key below.
    terrain_feasibility = _build_terrain_feasibility(db, user_id, cone)

    # Event Windows (#581 WS-H) — date-segment the REFRESH scope by the athlete's
    # declared event windows and resolve the existing cascade per reduced
    # environment, mirroring the create path. Scoped to [refresh_scope_start,
    # refresh_scope_end] because only those dates are re-synthesized; the segments
    # render into the refresh tier prompts (T1/T2/T3-intra + T3 cross-phase
    # Pattern A) and the declared-window digest folds into the refresh cache key
    # (a window edit already evicts plan_refresh too, so this only enables the
    # overlay RENDER on refresh — the create-first follow-up).
    event_window_segments, overlapping_windows = _build_event_window_overlay(
        db, user_id, cone,
        plan_start=refresh_scope_start, plan_end=refresh_scope_end,
        home_feasibility=terrain_feasibility,
    )
    event_windows_hash = (
        compute_event_windows_hash(overlapping_windows) if overlapping_windows else None
    )

    payload = llm_layer4_plan_refresh_cached(
        user_id=user_id,
        tier=tier,
        refresh_scope_start=refresh_scope_start,
        refresh_scope_end=refresh_scope_end,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2_bundle=layer2_bundle,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        prior_plan_session_window=prior_plan_session_window,
        parsed_intent=parsed_intent,
        plan_version_id=plan_version_id,
        plan_version_id_parent=plan_version_id_parent,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        plan_start_date=plan_start_date,
        # Thread the training-substitution payload from the cone into the
        # refresh prompt body + cache key.
        training_substitution_payload=cone.training_substitution_payload,
        # Thread the per-discipline terrain-feasibility resolutions into the
        # refresh prompt + cache key (#557, mirrors create).
        terrain_feasibility=terrain_feasibility,
        # Event Windows (#581 WS-H) — date-scoped reduced-environment segments
        # (refresh overlay) + the declared-window digest (cache key).
        event_window_segments=event_window_segments,
        event_windows_hash=event_windows_hash,
    )
    payload = _apply_locale_assign(db, user_id, payload, layer2_bundle.c)
    payload = _apply_rx_wire(db, user_id, payload, layer2_bundle.c)
    return payload


def orchestrate_plan_create(
    db: Any,
    user_id: int,
    *,
    plan_start_date: date,
    plan_version_id: int,
    cache: Layer4Cache,
    today: date | None = None,
) -> Layer4Payload:
    """End-to-end Pattern A plan-create pipeline for `user_id`.

    Algorithm:
    1. Load target race event (None OK — open-ended plans are first-class;
       Layer 3B's `mode='no-event'` branch handles this downstream and the
       driver accepts `race_event_payload=None` per `Layer4_Spec.md` §3.1).
    2. Compose upstream cone via `_upstream_full_cone` (shared with
       `orchestrate_race_week_brief` + `orchestrate_plan_refresh`).
    3. Compose via `llm_layer4_plan_create_cached`. The driver runs the
       per-phase synthesis loop (sequential, in order) + seam reviews +
       final cross-phase validator pass internally per §5.2; the
       orchestrator does not see per-phase internals.

    Pre-flight gates (3, all emitted by `_upstream_full_cone`):
    `etl_version_set_undiscoverable`, `primary_locale_missing`,
    `framework_sport_missing`. The orchestrator does NOT raise
    `no_target_event` (open-ended plans are supported) and does NOT
    pre-flight `plan_start_date_in_past` / `plan_version_id_unset` /
    `time_to_event_weeks_mismatch` / `discipline_weights_invalid` — the
    driver's `_validate_plan_create_inputs` covers all four per §4.2;
    `Layer4InputError` propagates verbatim, the orchestrator does not wrap
    (matches the slice 1 + slice 2 + race_week_brief precedent of not
    wrapping driver-level input errors).

    `plan_start_date` + `plan_version_id` are caller-supplied kwargs
    pending the D-64 caller-side route + `plan_versions` table (matches
    the slice 1 D4 + slice 2 D3 precedent for D-63/D-64 caller-side
    deferral). The route handler is the right place to resolve
    "athlete picks future start" vs "today" + allocate the `plan_versions`
    row.

    Note: this is the heaviest entry point. Pattern A fires N per-phase
    synthesizer calls (one per phase in `phase_structure_from_3b` output,
    typically 3-4) + (N-1) seam reviewer calls. Real-LLM cost ~$0.30-$0.50
    per cold synthesis; the per-entry §9.1 cache + per-phase §9.2 cache
    inside the engine short-circuit most repeat invocations.
    """
    if today is None:
        today = date.today()

    race_event = load_target_race_event_payload(db, user_id)
    cone = _upstream_full_cone(
        db, user_id, today, cache=cache, target_race_event=race_event,
        viability_current_date=plan_start_date,
    )

    layer2c_payloads = cone.layer2c_payloads
    # #540 slice 2c.2 — deterministic per-discipline terrain feasibility across
    # the locale cluster, resolved pre-synthesis so the synthesizer is handed a
    # session that already works (never a Rock Climbing session at a home with no
    # climbing terrain). Wired create-side first; refresh is the follow-up (§4.4).
    terrain_feasibility = _build_terrain_feasibility(db, user_id, cone)
    # Event Windows Slice 1 (#581 WS-H) — date-segment the plan span by the
    # athlete's declared event windows. The plan span is the same deterministic
    # phase_structure the engine rebuilds internally, so the overlapping-window
    # set (and thus the cache key) matches what the synthesis units render.
    total_weeks = _compute_total_weeks(cone.layer3b_payload, plan_start_date, race_event)
    phase_structure = phase_structure_from_3b(
        cone.layer3b_payload, plan_start_date, total_weeks=total_weeks
    )
    plan_end = (
        phase_structure.phases[-1].end_date
        if phase_structure.phases
        else plan_start_date
    )
    event_window_segments, overlapping_windows = _build_event_window_overlay(
        db, user_id, cone,
        plan_start=plan_start_date, plan_end=plan_end,
        home_feasibility=terrain_feasibility,
    )
    event_windows_hash = (
        compute_event_windows_hash(overlapping_windows) if overlapping_windows else None
    )
    payload = llm_layer4_plan_create_cached(
        user_id=user_id,
        layer1_payload=cone.layer1_payload.model_dump(mode="json"),
        layer2a_payload=cone.layer2a_payload,
        layer2b_payload=cone.layer2b_payload,
        layer2c_payloads=layer2c_payloads,
        layer2d_payload=cone.layer2d_payload,
        layer2e_payload=cone.layer2e_payload,
        layer3a_payload=cone.layer3a_payload,
        layer3b_payload=cone.layer3b_payload,
        plan_start_date=plan_start_date,
        plan_version_id=plan_version_id,
        etl_version_set=cone.etl_version_set,
        cache=cache,
        race_event_payload=race_event,
        # Thread the training-substitution payload from the cone into the
        # per-phase prompt bodies + cache key.
        training_substitution_payload=cone.training_substitution_payload,
        # Thread the per-discipline terrain-feasibility resolutions into the
        # session-grid prompt + cache key.
        terrain_feasibility=terrain_feasibility,
        # Event Windows Slice 1 — date-scoped reduced-environment segments
        # (synthesis overlay) + the declared-window digest (cache key).
        event_window_segments=event_window_segments,
        event_windows_hash=event_windows_hash,
    )
    payload = _apply_locale_assign(db, user_id, payload, layer2c_payloads)
    payload = _apply_rx_wire(db, user_id, payload, layer2c_payloads)
    # Layer 5A — stash the nutrition inputs (2E payload + body weight + event
    # dates) so the post-`ready` deterministic nutrition stage + the manual
    # regenerate action can rebuild without re-running this cone, pinned to
    # exactly what the plan was built on. Best-effort: a stash fault must NEVER
    # break plan generation, so it is isolated and never propagates. Reached
    # only on the completing pass (budget-incomplete passes raise before here);
    # the write rides the caller's transaction (committed at the ready-flip).
    _stash_plan_nutrition_inputs(db, user_id, plan_version_id, cone, race_event)
    return payload


def _stash_plan_nutrition_inputs(
    db: Any,
    user_id: int,
    plan_version_id: int,
    cone: "_UpstreamFullCone",
    race_event: Any,
) -> None:
    """Best-effort capture of the Layer 5A nutrition inputs for `plan_version_id`.

    WRITE-ONLY / advisory — never an input to a Layer 4 cache key. Isolated so
    any fault (a missing body weight, a serialization surprise) is logged and
    swallowed rather than failing the generation it rides alongside.
    """
    try:
        from plan_nutrition_repo import persist_plan_nutrition_inputs

        # Body weight is optional on Layer 1; without it the energy model can't
        # run, so skip cleanly (no stash) rather than persisting unusable inputs.
        body_weight = cone.layer1_payload.performance.body_weight_kg
        if body_weight is None or float(body_weight) <= 0:
            return

        event_dates: dict[str, str] = {}
        if race_event is not None:
            event_dates[str(race_event.race_event_id)] = (
                race_event.event_date.isoformat()
            )
        persist_plan_nutrition_inputs(
            db,
            user_id,
            plan_version_id,
            layer2e_payload_json=cone.layer2e_payload.model_dump(mode="json"),
            body_weight_kg=float(body_weight),
            event_dates=event_dates,
        )
    except Exception as exc:  # noqa: BLE001 — advisory stash must not break gen
        print(
            f"_stash_plan_nutrition_inputs: failed for "
            f"plan_version_id={plan_version_id} (non-fatal): {exc}"
        )


def _max_etl_version(versions: list[str]) -> str:
    """Return the highest ETL version by numeric ordering.

    Versions look like `0A-v11.0` / `0A-v9.0` / `0C-v2.0-r2`. A lexical MAX
    mis-sorts at a digit-width boundary (`'0A-v9.0' > '0A-v11.0'`), so compare
    the integer components as a tuple instead: `0A-v11.0` → `(0, 11, 0)`. A
    revision suffix (`-r2`) extends the tuple, so it correctly outranks the
    un-revised base of the same version.
    """
    return max(versions, key=lambda v: tuple(int(n) for n in re.findall(r"\d+", v)))


# Every versioned `layer0.*` table, mapped to its source family (`0A` sports,
# `0B` exercises, `0C` vocabulary/terrain/body-parts/equipment/conditions/
# toggles). Authoritative source: the `source_family=` argument on each
# `insert_versioned` call in `etl/layer0/run.py`. Family is a property of the
# *table*, not the version string — discovery does not parse the `0X-` prefix.
# `tests/test_layer4_orchestrator.py::TestLayer0TableFamilyMap` guards this
# against drift from the committed Layer 0 baseline snapshot
# (`etl/output/layer0_etl_v*.sql`); keep it in sync when a versioned table is
# added.
_LAYER0_TABLE_FAMILY: dict[str, str] = {
    # 0A — sports framework
    "sports": "0A",
    "disciplines": "0A",
    "sport_discipline_map": "0A",
    "discipline_pairing": "0A",
    "phase_load_allocation": "0A",
    "phase_load_weekly_totals": "0A",
    "team_formats": "0A",
    "cross_sport_properties": "0A",
    "sport_discipline_bridge": "0A",
    "discipline_substitutes": "0A",
    "discipline_training_gaps": "0A",
    "modality_groups": "0A",
    "discipline_modality_membership": "0A",
    "craft_discipline_aliases": "0A",
    # craft_terrain_compatibility (#586 WS-I) is created by migration 0004, not
    # schema.sql (like terrain_gap_rules); read by the unified craft/terrain
    # cascade. Same 0A family as its sibling craft_discipline_aliases.
    "craft_terrain_compatibility": "0A",
    # 0B — exercise library
    "exercises": "0B",
    "sport_exercise_map": "0B",
    # 0C — vocabulary / terrain / body-parts / equipment / conditions / toggles
    "body_parts": "0C",
    "health_condition_categories": "0C",
    "equipment_items": "0C",
    "terrain_types": "0C",
    "terrain_gap_rules": "0C",
    "sport_specific_gear_toggles": "0C",
    "skill_capability_toggles": "0C",
    "sport_name_aliases": "0C",
    # location_category_equipment_baseline (#581 WS-H Slice 3 / F8) is a 0C
    # serving table created by migration 0005 (not schema.sql); read via
    # locations.load_category_baselines to assume equipment/terrain for a
    # not-yet-logged locale. Registered so a baseline edit (supersede + bumped
    # etl_version) shifts the 0C digest → plan keys change → affected plans
    # re-synthesize on the new assumption.
    "location_category_equipment_baseline": "0C",
}
# Note: `layer0.supplement_vocabulary` (read by Layer 2E) is intentionally
# absent — it carries its own `supp_vocab.*` version line, not a 0A/0B/0C
# family prefix, and was never part of `etl_version_set`. It reads
# `WHERE superseded_at IS NULL` directly, so its edits serve live without a
# cache-key dependency (unchanged by slice 3b).


def _q_current_etl_version_set(db: Any) -> dict[str, str]:
    """Discover the active Layer 0 version fingerprint per source family.

    Returns `{"0A": …, "0B": …, "0C": …}` where each value is a digest of every
    table in that family at its current active version, e.g.
    `"sports=0A-v1.6.7;disciplines=0A-v1.6.8;…"`. The digest changes whenever
    *any* table in the family changes its active version, so a single-table
    migration invalidates the plan-gen caches that fold `etl_version_set` into
    their key — without a whole-family re-stamp (slice 3b, epic #488).

    Serving itself no longer matches on `etl_version`: the Layer 2 builders read
    `WHERE superseded_at IS NULL` and pick up the active row set directly, so a
    migration is observed the moment it commits. The version digest exists only
    as the cache-invalidation signal (per-table, so no advance-the-max foot-gun)
    and the version provenance carried on each payload.

    Per-table max (see `_max_etl_version`) tolerates the transient in-migration
    state where a table briefly holds two active versions; the steady state is
    one active version per table.
    """
    union = " UNION ALL ".join(
        f"SELECT DISTINCT '{table}' AS tbl, etl_version AS v "
        f"FROM layer0.{table} WHERE superseded_at IS NULL"
        for table in _LAYER0_TABLE_FAMILY
    )
    cur = db.execute(f"SELECT tbl, v FROM ({union}) members")

    by_family: dict[str, dict[str, list[str]]] = {"0A": {}, "0B": {}, "0C": {}}
    for row in cur.fetchall():
        version = row["v"]
        if not version:
            continue
        family = _LAYER0_TABLE_FAMILY.get(row["tbl"])
        if family is None:
            continue
        by_family[family].setdefault(row["tbl"], []).append(version)

    version_set: dict[str, str] = {}
    for family, tables in by_family.items():
        if not tables:
            raise OrchestrationError(
                "etl_version_set_undiscoverable",
                f"layer0 family {family} has no non-superseded rows",
            )
        version_set[family] = ";".join(
            f"{table}={_max_etl_version(versions)}"
            for table, versions in sorted(tables.items())
        )
    return version_set


def _q_primary_locale(db: Any, user_id: int) -> str:
    """Return the athlete's home locale slug — the `locale_profiles` row with
    `preferred = TRUE` (Locations_Consolidation_Design_v1 §5.1). Replaces the
    hardcoded `locale = 'home'` convention. Delegates to the authoritative
    `locations.primary_locale`; re-raises its domain error as the
    layer-contract `OrchestrationError("primary_locale_missing")`.
    """
    try:
        return locations.primary_locale(db, user_id)
    except locations.PrimaryLocaleMissing as exc:
        raise OrchestrationError("primary_locale_missing", str(exc)) from exc


def _q_locale_equipment_pool(db: Any, user_id: int, locale: str) -> list[str]:
    """Return the canonical-name equipment pool effective at a single
    `locale`, via the authoritative `locations.locale_effective_tags`. Used by
    the single-session path (one athlete-picked locale); the full plan-gen
    cone unions across the cluster (`locations.cluster_effective_tags`)."""
    return sorted(locations.locale_effective_tags(db, user_id, locale))


def _q_locale_by_slug(db: Any, user_id: int, locale: str) -> bool:
    """Return True when `(user_id, locale)` has a `locale_profiles` row.

    Used by `orchestrate_single_session_synthesize` to validate the
    athlete-picked `request.locale_slug` before composing the 2C call.
    Distinct from `_q_primary_locale` (which is hard-coded to `'home'`):
    single-session athletes pick any locale they've configured.
    """
    cur = db.execute(
        "SELECT 1 AS hit FROM locale_profiles WHERE user_id = ? AND locale = ? LIMIT 1",
        (user_id, locale),
    )
    return cur.fetchone() is not None


def _q_locale_terrain_ids(db: Any, user_id: int, locale: str) -> list[str]:
    """Return canonical TRN-xxx terrain ids available at `locale`.

    Reads `locale_profiles.locale_terrain_ids` (TEXT[]) for the
    (user_id, locale) row. Returns `[]` when the row carries an empty
    array or NULL (athlete hasn't yet captured terrain via Form-refresh C);
    Layer 2B's `_validate_inputs` accepts the empty case (spec §4
    condition 5 + §13.3). Psycopg2 hydrates TEXT[] to a Python list
    directly; the SQLite shim path returns the JSON-ish text representation
    that `_hydrate_locale_terrain_ids` already covers route-side, but the
    orchestrator is PG-only so the list-path is the only live shape here.
    Tolerates the JSON-string SQLite shim for completeness (mirrors
    `race_events_repo.get_race_event` adapter tolerance for race_terrain).
    """
    cur = db.execute(
        """SELECT locale_terrain_ids
             FROM locale_profiles
            WHERE user_id = ? AND locale = ?
            LIMIT 1""",
        (user_id, locale),
    )
    row = cur.fetchone()
    if row is None:
        return []
    raw = row["locale_terrain_ids"]
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s in ("{}", "[]"):
            return []
        # SQLite shim path — tolerate JSON-string array. Postgres TEXT[]
        # arrives as a list already.
        import json as _json
        try:
            parsed = _json.loads(s)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [v for v in parsed if isinstance(v, str)]
    return []


__all__ = [
    "OrchestrationError",
    "orchestrate_plan_create",
    "orchestrate_plan_refresh",
    "orchestrate_race_week_brief",
    "orchestrate_single_session_synthesize",
]
