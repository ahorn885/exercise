"""Deterministic per-discipline session feasibility resolution — Track 2
slice 2c.2 (issue #540), terrain axis.

The deterministic session grid (`session_grid.build_session_grid`) decides how
many sessions of each discipline a week wants; the LLM then composes and places
them. The pv=65 review surfaced a gap: the synthesizer could place a session
the athlete *cannot physically do* — a Rock Climbing session at a home with no
climbing terrain. This module closes that gap deterministically, BEFORE the
LLM composes, so the synthesizer is handed a session that already works.

For each discipline the grid wants, `resolve_terrain_feasibility` runs a
cascade against the athlete's whole locale CLUSTER (home + nearby saved
locales — not just home):

  1. EXACT      — a cluster locale carries one of the discipline's required
                  terrains → schedule there on real terrain.
  2. PROXY      — no required terrain anywhere, but a cluster locale has a
                  next-best terrain (a `terrain_gap_rules` proxy at/above the
                  fidelity floor) → schedule there as a proxy (e.g. Mountain
                  Biking with no off-road terrain becomes a road ride).
  3. INDOOR     — a cluster locale has the discipline's indoor cardio machine
                  (treadmill / stair climber / erg / trainer) → indoor session.
  4. STRENGTH   — nothing rideable/runnable: substitute a strength session
                  built from the discipline's own mapped exercises (Layer 2C
                  `ResolvedExercise.discipline_ids`, equipment-feasible at a
                  cluster locale), targeting the discipline's muscles. This is
                  the climbing-with-no-gym fix — a real pulling/grip session.
  5. REALLOCATE — only when even strength yields nothing (rare): don't
                  prescribe the impossible session; its time is reallocated.

The resolver is pure (no DB, no LLM): the orchestrator gathers the cluster
terrain/equipment maps + gap rules + the discipline→exercise sets from existing
readers and hands them in. Craft disciplines (bike/paddle) instead walk the
unified `resolve_craft_terrain_feasibility` cascade (#586 WS-I, below), which
composes craft ownership with terrain off `layer0.craft_terrain_compatibility`;
this terrain-only resolver still owns the non-craft (foot/swim/climb) disciplines.

Discipline→required-terrain and discipline→indoor-machine are Python constants
here, not Layer 0 columns — the same precedent as the route keeping its own
`RACE_INELIGIBLE_TERRAIN_IDS`. Lifting them to `layer0` is Track-3-gated and
filed as a follow-up to #540.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any, Literal

# Below this proxy fidelity a `terrain_gap_rules` proxy is not worth scheduling
# the session on — fall through to the indoor machine / strength tiers instead.
# Aligned with the Layer 2 training-substitution `_UNTRAINABLE_FIDELITY_FLOOR`.
_PROXY_FIDELITY_FLOOR = 0.25


# ─── Discipline → required terrains (any-of) ─────────────────────────────────
# A session is feasible on real terrain at a locale that carries ANY of these.
# Disciplines absent from this map carry no terrain requirement (e.g. Obstacle
# Course Racing, whose mixed terrain isn't in the vocab) — they resolve to home
# untouched and emit no guidance. Terrain ids are the live `layer0.terrain_types`
# vocab (genesis v1.6.7, 19 active rows). D-018 Mountaineering = Mountain/Alpine
# + Technical Rock/Scree + Snow (Andy 2026-06-11).
_DISCIPLINE_REQUIRED_TERRAINS: dict[str, frozenset[str]] = {
    "D-001": frozenset({"TRN-002", "TRN-003", "TRN-004"}),          # Trail Running
    "D-002": frozenset({"TRN-001"}),                                 # Road Running
    "D-003": frozenset({"TRN-002", "TRN-003", "TRN-004", "TRN-005", "TRN-018"}),  # Trekking
    "D-004": frozenset({"TRN-008", "TRN-009", "TRN-010"}),          # Swimming
    "D-006": frozenset({"TRN-001"}),                                 # Road Cycling
    "D-007": frozenset({"TRN-001"}),                                 # Time-Trial Cycling
    "D-008": frozenset({"TRN-002", "TRN-003", "TRN-015"}),          # Mountain Biking
    "D-009": frozenset({"TRN-009", "TRN-010", "TRN-011", "TRN-017"}),  # Packrafting
    "D-010": frozenset({"TRN-009", "TRN-010", "TRN-011", "TRN-017"}),  # Kayaking
    "D-011": frozenset({"TRN-009", "TRN-017"}),                      # Canoeing
    "D-012": frozenset({"TRN-013", "TRN-014"}),                      # Rock Climbing
    "D-013": frozenset({"TRN-013", "TRN-014"}),                      # Abseiling
    "D-014": frozenset({"TRN-005", "TRN-013"}),                      # Via Ferrata
    "D-017": frozenset({"TRN-012"}),                                 # Snowshoeing
    "D-018": frozenset({"TRN-005", "TRN-007", "TRN-012"}),          # Mountaineering
    "D-019": frozenset({"TRN-009", "TRN-011", "TRN-017"}),          # Paddle Rafting
    "D-021": frozenset({"TRN-012"}),                                 # Uphill Skinning
    "D-022": frozenset({"TRN-012"}),                                 # Alpine Descent
    "D-024": frozenset({"TRN-002", "TRN-003", "TRN-004", "TRN-005"}),  # Mountain Running
    "D-028": frozenset({"TRN-012"}),                                 # Cross-Country Skiing
    "D-030": frozenset({"TRN-020", "TRN-001"}),                      # Gravel Cycling
    "D-031": frozenset({"TRN-002", "TRN-003", "TRN-020"}),          # Cross Country Cycling
    "D-032": frozenset({"TRN-009", "TRN-010", "TRN-017"}),          # Stand-up Paddleboard
}


# ─── Discipline → indoor cardio machine(s) (canonical equipment names) ───────
# The INDOOR tier fires when a cluster locale's equipment pool carries any of
# these. All names are live `layer0.equipment_items` canonical tags (verified
# present in genesis v1.6.7) — no equipment vocab additions. Disciplines whose
# only honest indoor option is the terrain itself (Swimming → Pool) or a
# strength substitute (climbing) intentionally have no machine.
_DISCIPLINE_INDOOR_MACHINES: dict[str, tuple[str, ...]] = {
    "D-001": ("Treadmill",),
    "D-002": ("Treadmill",),
    "D-003": ("Treadmill", "Stair climber"),
    "D-017": ("Treadmill", "Stair climber"),
    "D-018": ("Stair climber", "Treadmill"),
    "D-021": ("Ski erg", "Stair climber"),
    "D-022": ("Ski erg",),
    "D-024": ("Treadmill", "Stair climber"),
    "D-028": ("Ski erg",),
    # #692 — `Spin bike`/`Stationary bike` were retired from the equipment picker
    # (layer0 migration 0012, folded into `Cycling trainer`). They stay listed
    # here so an athlete who *already* saved one keeps indoor routing; new gear
    # is captured as `Cycling trainer`/`Assault bike`.
    "D-006": ("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike"),
    "D-007": ("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike"),
    "D-008": ("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike"),
    "D-030": ("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike"),
    "D-031": ("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike"),
    "D-009": ("Paddle ergometer", "Rowing ergometer"),
    "D-010": ("Paddle ergometer", "Rowing ergometer"),
    "D-011": ("Paddle ergometer", "Rowing ergometer"),
    "D-019": ("Paddle ergometer", "Rowing ergometer"),
    "D-032": ("Paddle ergometer", "Rowing ergometer"),
}


# ─── Resolution result ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class TerrainResolution:
    """The deterministic resolution for one discipline this plan. `tier` drives
    the synthesis-prompt guidance; `note` is the rendered human-readable line.

    - exact      → schedule the discipline as-is at `locale_id` on `terrain_id`.
    - proxy      → schedule at `locale_id` on the proxy `terrain_id`
                   (`proxy_fidelity` set); the discipline trains in a degraded
                   surface (e.g. MTB → road ride).
    - indoor     → schedule an indoor session at `locale_id` on `machine`.
    - strength   → substitute a strength session at `locale_id` from
                   `substitute_exercise_ids` (the discipline's mapped pool).
    - reallocate → infeasible everywhere; do not schedule (`locale_id` None).
    """

    discipline_id: str
    tier: Literal["exact", "proxy", "indoor", "strength", "reallocate"]
    locale_id: str | None
    terrain_id: str | None = None
    proxy_fidelity: float | None = None
    machine: str | None = None
    substitute_exercise_ids: list[str] = field(default_factory=list)
    note: str = ""
    # Craft overlay, set by the unified craft/terrain cascade (#586 WS-I). ""
    # → no craft action (terrain line renders untouched: own-craft exact/alt, or
    # a non-craft discipline). "proxy" → real terrain on a proxy craft you own
    # (cascade tier 3); `owned_craft` names the proxy, the sport is unchanged.
    # "swap" → ride the proxy on its OWN terrain (tier 4); `craft_swap_to_name`
    # + `owned_craft` render the "train as X" prefix. "strength" → a craft
    # terminal (own no craft of the kind); `tier` is "strength" and `craft_kind`
    # supplies the reason in place of the terrain one.
    craft_tier: Literal["", "swap", "strength", "proxy"] = ""
    owned_craft: str | None = None
    craft_swap_to_name: str = ""
    craft_kind: str = ""
    # Deterministic venue display (#624 / #618-7), attached post-resolution by the
    # orchestrator (`enrich_resolution_display`) where DB reads live. The pure
    # cascade leaves these defaulted; the synthesis line falls back to the slug.
    # - locale_name / locale_distance_km: display name + km of `locale_id` (every
    #   tier) — the synthesizer cites the saved locale by name, never the slug.
    # - terrain_venues: EXACT only (non-craft, or craft own/proxy tier constrained
    #   to the craft's rideable terrains — #624 Slice 3) — each candidate terrain
    #   present in the cluster mapped to its NEAREST carrying locale, nearest-first, as
    #   (terrain_name, locale_name, distance_km). The menu that grounds the
    #   synthesizer in real nearby surfaces ('Groomed Trail at Cleburne, 18 km')
    #   so it can't claim 'no nearby groomed trail' or invent a farther park.
    locale_name: str | None = None
    locale_distance_km: float | None = None
    terrain_venues: tuple[tuple[str, str, float | None], ...] = ()
    # Surface-specific routing (#624), attached by `enrich_resolution_display`
    # when `terrain_attrs` is supplied. EXACT only (non-craft, or craft own/proxy
    # tier — #624 Slice 3 — with candidates constrained to the craft's rideable
    # terrains): the nearest carrying venue PER training purpose among the
    # candidate surfaces, as (purpose_label, terrain_name, locale_name, distance_km), in
    # coaching order. Emitted only when ≥2 distinct purposes map to ≥2 distinct
    # locales (otherwise routing is a no-op and `terrain_venues` renders). Lets
    # the synthesizer send each session to the surface its purpose calls for
    # (long aerobic → groomed/flat; hill work → hills) instead of collapsing
    # every session onto the nearest surface.
    surface_routes: tuple[tuple[str, str, str, float | None], ...] = ()


# ─── Surface training-purpose taxonomy (#624 surface-specific routing) ────────
# A multi-surface discipline routes each KIND of session to the surface that
# trains it. The purpose a surface serves is DERIVED from the live
# `layer0.terrain_types` attributes (`requires_elevation` / `technical_surface`)
# — no new vocab: elevation surfaces carry hill/vert work, non-elevation
# technical surfaces carry skill work, and flat non-technical surfaces carry
# easy/long aerobic volume. A surface that is BOTH elevation and technical
# (Mountain/Alpine, Fell) routes to vert — the elevation stimulus dominates.
SURFACE_AEROBIC = "easy / long aerobic"
SURFACE_VERT = "hill / vert work"
SURFACE_TECHNICAL = "technical / skill work"

# Coaching render order: aerobic base, then vert quality, then technical skill.
_SURFACE_PURPOSE_ORDER = (SURFACE_AEROBIC, SURFACE_VERT, SURFACE_TECHNICAL)


def surface_purpose(requires_elevation: bool, technical_surface: bool) -> str:
    """The training purpose a surface serves, from its `layer0.terrain_types`
    attributes. Elevation dominates technical when both are set."""
    if requires_elevation:
        return SURFACE_VERT
    if technical_surface:
        return SURFACE_TECHNICAL
    return SURFACE_AEROBIC


def required_terrains(discipline_id: str) -> frozenset[str]:
    """The any-of terrain set for a discipline (empty when unconstrained)."""
    return _DISCIPLINE_REQUIRED_TERRAINS.get(discipline_id, frozenset())


def indoor_machines(discipline_id: str) -> tuple[str, ...]:
    """The indoor cardio machine tags that can stand in for a discipline."""
    return _DISCIPLINE_INDOOR_MACHINES.get(discipline_id, ())


def resolve_terrain_feasibility(
    discipline_id: str,
    *,
    locale_order: list[str],
    cluster_terrain_by_locale: dict[str, set[str]],
    cluster_equipment_by_locale: dict[str, set[str]],
    gap_rules: dict[str, list[tuple[str, float]]],
    discipline_exercise_ids: list[str],
    fidelity_floor: float = _PROXY_FIDELITY_FLOOR,
) -> TerrainResolution | None:
    """Resolve where/how one discipline's sessions can be done this plan.

    Pure. Returns None when the discipline carries no terrain requirement
    (nothing to constrain — the synthesizer schedules it normally). Otherwise
    runs the EXACT → PROXY → INDOOR → STRENGTH → REALLOCATE cascade.

    Args:
        discipline_id: the discipline the grid wants.
        locale_order: cluster locale ids, deterministic and NEAREST-first
            (`locations.cluster_locale_ids` haversine-sorts the cluster, home at
            0 km). The first satisfying locale wins at each tier → the nearest
            satisfying locale (the deterministic venue pick, #624).
        cluster_terrain_by_locale: locale_id → set of available TRN-xxx ids.
        cluster_equipment_by_locale: locale_id → set of canonical equipment tags.
        gap_rules: required-terrain id → [(proxy TRN id, fidelity), ...]
            (`layer0.terrain_gap_rules`, proxy_terrain_id NOT NULL).
        discipline_exercise_ids: exercise ids mapped to this discipline that are
            equipment-feasible somewhere in the cluster, ranked best-first — the
            strength-substitute pool.
        fidelity_floor: minimum proxy fidelity worth scheduling a session on.
    """
    required = required_terrains(discipline_id)
    if not required:
        return None

    # ── 1. EXACT — a cluster locale carries a required terrain ───────────────
    for locale in locale_order:
        have = cluster_terrain_by_locale.get(locale, set())
        match = required & have
        if match:
            terrain = sorted(match)[0]
            return TerrainResolution(
                discipline_id=discipline_id,
                tier="exact",
                locale_id=locale,
                terrain_id=terrain,
                note=f"{terrain} available at {locale}",
            )

    # ── 2. PROXY — next-best terrain (gap-rule proxy) in the cluster ─────────
    # Best candidate = highest fidelity at/above the floor; locale_order breaks
    # fidelity ties (earlier locale wins).
    best: tuple[float, int, str, str] | None = None  # (fidelity, -order, locale, proxy)
    for req in sorted(required):
        for proxy, fidelity in gap_rules.get(req, []):
            if fidelity < fidelity_floor:
                continue
            for idx, locale in enumerate(locale_order):
                if proxy in cluster_terrain_by_locale.get(locale, set()):
                    cand = (fidelity, -idx, locale, proxy)
                    if best is None or cand > best:
                        best = cand
    if best is not None:
        fidelity, _negidx, locale, proxy = best
        return TerrainResolution(
            discipline_id=discipline_id,
            tier="proxy",
            locale_id=locale,
            terrain_id=proxy,
            proxy_fidelity=fidelity,
            note=(
                f"no required terrain in cluster; nearest-surface proxy {proxy} "
                f"at {locale} (fidelity {fidelity:.2f})"
            ),
        )

    # ── 3. INDOOR — discipline's cardio machine in a cluster locale's pool ───
    machines = indoor_machines(discipline_id)
    if machines:
        for locale in locale_order:
            pool = cluster_equipment_by_locale.get(locale, set())
            for machine in machines:
                if machine in pool:
                    return TerrainResolution(
                        discipline_id=discipline_id,
                        tier="indoor",
                        locale_id=locale,
                        machine=machine,
                        note=f"indoor {machine} at {locale}",
                    )

    # ── 4. STRENGTH — substitute a strength session from the mapped pool ─────
    if discipline_exercise_ids:
        # Place the session where the gear actually is: the first cluster locale
        # (home-first) that carries any equipment — the gym — falling back to
        # home when no locale lists equipment (bodyweight-feasible at home).
        # Mirrors the INDOOR tier's "first locale that satisfies" locale choice.
        locale = next(
            (loc for loc in locale_order if cluster_equipment_by_locale.get(loc)),
            locale_order[0] if locale_order else None,
        )
        return TerrainResolution(
            discipline_id=discipline_id,
            tier="strength",
            locale_id=locale,
            substitute_exercise_ids=list(discipline_exercise_ids),
            note=(
                "no terrain, proxy, or machine available — substitute a strength "
                "session targeting this discipline's demands"
            ),
        )

    # ── 5. REALLOCATE — nothing works anywhere ───────────────────────────────
    return TerrainResolution(
        discipline_id=discipline_id,
        tier="reallocate",
        locale_id=None,
        note="infeasible in your locale cluster — reallocate this session's time",
    )


# ─── Unified gear/terrain cascade (#586 WS-I + #884 slice 4b, design §3/§6) ───
# Gear-bearing disciplines walk ONE ordered cascade that composes gear ownership
# with terrain — replacing the old two-non-composing-axes split (a craft ladder
# that short-circuited ahead of terrain, so a craftless athlete with a trainer
# was sent to STRENGTH instead of the INDOOR machine they own). Non-gear
# disciplines (foot/swim) keep the terrain-only `resolve_terrain_feasibility`
# cascade untouched.
#
# For each owned gear item in priority order (the discipline's own gear first,
# then same-`group_kind` proxy gear) a terrain sub-check runs — can the gear ride
# a required terrain that's in-cluster? then any terrain it's compatible with? —
# before falling through to indoor → strength → reallocate. "Gearless" is not a
# special branch: tiers 1–4 simply all miss and the walk lands on INDOOR (tier 5).
# Which terrains a gear item operates on is read explicitly from
# `layer0.craft_terrain_compatibility` (design §4) — NOT derived from the
# discipline graph, so a road bike and a gravel bike (both aliasing road/XC
# disciplines) differ on singletrack.
#
# #884 slice 4b generalizes the gate from {bike, paddle} to every
# discipline-unlocking gear kind. Two seams matter:
#   - The discipline's gear kind is read from `gear_discipline_aliases`
#     (`discipline_gear_kind`), NOT from `modality_groups.group_kind`. The gear
#     taxonomy is FINER than the modality one — the single modality 'snow' splits
#     into the gear families 'ski' / 'snow' / 'alpine' (so snowshoes never proxy
#     for skis), which have no modality-vocab name. (The shared kinds — bike,
#     paddle, snow, climb — are named identically across both, #884 slice 4b.)
#     So the gear-side kind is the only one that matches owned gear; for bike/
#     paddle the two coincide, so this is byte-identical there.
#   - Owned same-kind gear is walked by ASCENDING `fidelity_rank` (0 = best). The
#     D-028 ski ladder is the case that needs it: classic(0) → skate(1) →
#     rollerskis(2, dryland). Bike/paddle gear is all rank 0 → the prior slug sort.
# Swim gear is excluded (it drill-gates cardio drills, slice 3b — not a terrain
# axis); it carries no `gear_discipline_aliases` row, so it never enters here.
_CRAFT_GROUP_KINDS = frozenset(
    {"bike", "paddle", "ski", "snow", "climb", "alpine"}
)


def resolve_craft_terrain_feasibility(
    discipline_id: str,
    *,
    owned_crafts: list[str],
    craft_disciplines: dict[str, list[str]],
    craft_group_kind: dict[str, str],
    discipline_groups: dict[str, list[str]],
    discipline_gear_kind: dict[str, str],
    craft_terrain: dict[str, set[str]],
    craft_fidelity_rank: dict[str, int] | None = None,
    locale_order: list[str],
    cluster_terrain_by_locale: dict[str, set[str]],
    cluster_equipment_by_locale: dict[str, set[str]],
    discipline_exercise_ids: list[str],
    discipline_names: dict[str, str] | None = None,
) -> TerrainResolution | None:
    """The unified gear/terrain cascade for one gear-bearing discipline
    (design §3, generalized to all gear kinds in #884 slice 4b §6).

    Pure. Returns None when the discipline has no gear axis — `discipline_gear_kind`
    (read from `gear_discipline_aliases`) has no craft-kind entry for it — and the
    caller runs the terrain-only cascade instead. Otherwise walks the 7-tier
    cascade (first match wins):

      1. own the discipline's craft AND it can ride a required terrain in-cluster
      2. own the craft; ride it on an alternate terrain it's compatible with
      3. own a same-kind PROXY craft that can ride the DESIRED (required) terrain
      4. own a proxy craft; ride it on ITS OWN terrain → swap to the proxy's sport
      5. INDOOR — a trainer/erg for this discipline is in the equipment pool
      6. STRENGTH — substitute from the discipline's mapped pool
      7. REALLOCATE — nothing available

    Tier 3 ranks above tier 4 (Andy-ratified): desired-terrain-on-a-proxy beats
    proxy-on-its-own-terrain.

    Args mirror `resolve_craft_feasibility`'s predecessor plus the terrain inputs
    of `resolve_terrain_feasibility`; `craft_terrain` is
    `{gear_id: {TRN-xxx, ...}}` from `layer0.craft_terrain_compatibility`.
    `discipline_gear_kind` is `{discipline_id: gear group_kind}` from
    `gear_discipline_aliases` (the gear-side kind, which may differ from the
    discipline's modality kind). `craft_fidelity_rank` is `{gear_id: rank}` (0 =
    best) from the same table; absent/None → all rank 0 (the pre-4b ordering).
    """
    my_groups = set(discipline_groups.get(discipline_id, []))
    target_kind = discipline_gear_kind.get(discipline_id)
    if target_kind not in _CRAFT_GROUP_KINDS:
        # No gear axis for this discipline (no `gear_discipline_aliases` row, or a
        # swim drill-gating kind) — the caller runs the terrain-only cascade.
        return None

    required = required_terrains(discipline_id)
    # Walk owned same-kind gear by ASCENDING fidelity_rank (0 = best), slug-
    # breaking ties. Bike/paddle gear is all rank 0 → identical to the prior slug
    # sort (byte-identical); the D-028 ski ladder walks classic(0) → skate(1) →
    # rollerskis(2) best-first.
    ranks = craft_fidelity_rank or {}
    same_kind = sorted(
        (c for c in set(owned_crafts) if craft_group_kind.get(c) == target_kind),
        key=lambda c: (ranks.get(c, 0), c),
    )

    def _trains(c: str) -> bool:
        """True when craft `c` is the discipline's OWN craft — directly aliased
        to it, or to a sibling discipline sharing its modality group."""
        c_discs = craft_disciplines.get(c, [])
        return discipline_id in c_discs or any(
            my_groups & set(discipline_groups.get(cd, [])) for cd in c_discs
        )

    own_crafts = [c for c in same_kind if _trains(c)]
    proxy_crafts = [c for c in same_kind if c not in own_crafts]
    names = discipline_names or {}

    def _first(allowed: frozenset[str] | set[str]) -> tuple[str, str] | None:
        """First (locale, terrain) in locale_order where an allowed terrain is
        present — home-first deterministic, mirrors the terrain cascade."""
        for locale in locale_order:
            have = cluster_terrain_by_locale.get(locale, set()) & allowed
            if have:
                return locale, sorted(have)[0]
        return None

    # ── Tier 1: own the discipline's craft, ride its REQUIRED terrain ────────
    for c in own_crafts:
        hit = _first(required & craft_terrain.get(c, set()))
        if hit:
            locale, terrain = hit
            return TerrainResolution(
                discipline_id, "exact", locale, terrain_id=terrain, owned_craft=c,
                note=f"own {c}; required terrain {terrain} in cluster at {locale}",
            )

    # ── Tier 2: own the craft, ride an ALTERNATE terrain it's compatible with ─
    for c in own_crafts:
        hit = _first(craft_terrain.get(c, set()) - required)
        if hit:
            locale, terrain = hit
            return TerrainResolution(
                discipline_id, "proxy", locale, terrain_id=terrain, owned_craft=c,
                note=(
                    f"own {c}; no required terrain in cluster — alternate surface "
                    f"{terrain} at {locale}"
                ),
            )

    # ── Tier 3: PROXY craft on the DESIRED (required) terrain ────────────────
    for c in proxy_crafts:
        hit = _first(required & craft_terrain.get(c, set()))
        if hit:
            locale, terrain = hit
            return TerrainResolution(
                discipline_id, "exact", locale, terrain_id=terrain,
                craft_tier="proxy", owned_craft=c,
                note=f"proxy craft {c} can ride required {terrain} at {locale}",
            )

    # ── Tier 4: PROXY craft on ITS OWN terrain → swap to the proxy's sport ───
    for c in proxy_crafts:
        hit = _first(craft_terrain.get(c, set()) - required)
        if hit:
            locale, terrain = hit
            c_discs = sorted(craft_disciplines.get(c, []))
            swap_to = c_discs[0] if c_discs else discipline_id
            return TerrainResolution(
                discipline_id, "exact", locale, terrain_id=terrain,
                craft_tier="swap", owned_craft=c,
                craft_swap_to_name=names.get(swap_to, swap_to),
                note=f"own {c}; train this allocation as {swap_to} on {terrain} at {locale}",
            )

    # ── Tier 5: INDOOR — trainer/erg in the equipment pool (craft-independent) ─
    machines = indoor_machines(discipline_id)
    if machines:
        for locale in locale_order:
            pool = cluster_equipment_by_locale.get(locale, set())
            for machine in machines:
                if machine in pool:
                    return TerrainResolution(
                        discipline_id, "indoor", locale, machine=machine,
                        note=f"no rideable terrain in cluster — indoor {machine} at {locale}",
                    )

    # ── Tier 6: STRENGTH — substitute from the discipline's mapped pool ───────
    # Craftless (own no craft of the kind) flags the craft reason; owning a craft
    # but lacking terrain/machine keeps the terrain reason (craft_tier="").
    if discipline_exercise_ids:
        locale = next(
            (loc for loc in locale_order if cluster_equipment_by_locale.get(loc)),
            locale_order[0] if locale_order else None,
        )
        craftless = not same_kind
        return TerrainResolution(
            discipline_id, "strength", locale,
            substitute_exercise_ids=list(discipline_exercise_ids),
            craft_tier="strength" if craftless else "",
            craft_kind=target_kind if craftless else "",
            note="no rideable craft/terrain or indoor machine — substitute strength",
        )

    # ── Tier 7: REALLOCATE — nothing works anywhere ───────────────────────────
    return TerrainResolution(
        discipline_id, "reallocate", None,
        note="no craft, terrain, machine, or strength pool — reallocate this time",
    )


# ─── Synthesis-prompt rendering ──────────────────────────────────────────────
# The resolution is internal synthesis guidance, rendered into the deterministic
# session-grid block the same way that block already surfaces discipline ids /
# TRN ids; the synthesizer is instructed elsewhere to translate to natural
# language in its output. Two surfaces (mirroring #336's skill-capability gate):
#   - `feasibility_line`  — the full per-discipline guidance line, rendered once
#     in the dedicated feasibility block.
#   - `grid_annotation`   — a short inline tag on the authoritative count line,
#     only for the tiers that change the session KIND (strength) or drop it
#     (reallocate), so the count is never read as the as-prescribed sport.


def _venue_label(
    name: str | None, slug: str | None, distance_km: float | None
) -> str:
    """A locale reference for the synthesis line: the display NAME (never the
    slug) in quotes, suffixed with its distance from home. '(home)' at ~0 km;
    no suffix when distance is unknown (manual-entry locale)."""
    base = name or (slug.replace("_", " ").title() if slug else "your locale")
    label = f'"{base}"'
    if distance_km is None:
        return label
    if distance_km <= 0.1:
        return f"{label} (home)"
    return f"{label} ({distance_km:.0f} km away)"


def enrich_resolution_display(
    resolution: TerrainResolution,
    *,
    locale_order: list[str],
    locale_meta: dict[str, dict[str, Any]],
    terrain_names: dict[str, str],
    terrain_by_locale: dict[str, set[str]],
    terrain_attrs: dict[str, dict[str, bool]] | None = None,
    craft_terrain: dict[str, set[str]] | None = None,
) -> TerrainResolution:
    """Attach deterministic venue display data to a resolved discipline (#624 /
    #618-7) so the synthesis feasibility line cites the athlete's real saved
    locales by NAME + distance rather than leaking a slug or letting the LLM
    invent a venue. Pure — the maps come from the orchestrator's DB reads.

    Fills `locale_name` / `locale_distance_km` for the scheduling locale (every
    tier). For the EXACT terrain tier (non-craft), also computes `terrain_venues`:
    each required terrain present anywhere in the cluster mapped to its NEAREST
    carrying locale (`locale_order` is distance-sorted), nearest-first — the menu
    that grounds the synthesizer in every real nearby surface.

    When `terrain_attrs` (`{terrain_id: {requires_elevation, technical_surface}}`)
    is supplied, also computes `surface_routes` (#624): the nearest carrying venue
    PER training purpose, emitted only when ≥2 distinct purposes map to ≥2 distinct
    locales — the routing that sends each session to the surface its purpose calls
    for. Bare callers (no attrs) get the unchanged menu behavior.

    For craft disciplines (#624 Slice 3): EXACT own-craft (tier 1) and proxy-craft
    (tier 3) resolutions get the same venue menu + surface routing, BUT the
    candidate surfaces are intersected with the resolved craft's rideable terrains
    (`craft_terrain[owned_craft]`) so a paddle/bike session is never routed to a
    required surface the craft cannot actually traverse. The SWAP tier (the sport
    itself changes) is left untouched. Non-craft callers pass `craft_terrain=None`
    → byte-identical to the pre-Slice-3 behavior."""
    loc = resolution.locale_id
    meta = locale_meta.get(loc) if loc is not None else None
    name = meta.get("name") if meta else None
    dist = meta.get("distance_km") if meta else None

    venues: tuple[tuple[str, str, float | None], ...] = ()
    routes: tuple[tuple[str, str, str, float | None], ...] = ()
    if resolution.tier == "exact" and resolution.craft_tier in ("", "proxy"):
        # Candidate surfaces = the discipline's required terrains, intersected with
        # what the resolved craft can ride (#624 Slice 3) so a craft session is
        # never routed to a surface its craft can't traverse. Non-craft (no
        # owned_craft / no craft_terrain) → unconstrained, as before.
        cand_terrains: frozenset[str] | set[str] = required_terrains(
            resolution.discipline_id
        )
        if resolution.owned_craft is not None and craft_terrain is not None:
            cand_terrains = cand_terrains & craft_terrain.get(
                resolution.owned_craft, set()
            )
        # (sortkey, terrain_name, locale_name, distance, purpose) — the nearest
        # carrier per candidate terrain (locale_order is distance-sorted, so the
        # first carrier seen is the nearest).
        rows: list[tuple[float, str, str, float | None, str | None]] = []
        for terr in cand_terrains:
            for cand in locale_order:  # distance-sorted → first carrier = nearest
                if terr in terrain_by_locale.get(cand, set()):
                    cmeta = locale_meta.get(cand) or {}
                    cdist = cmeta.get("distance_km")
                    attrs = (terrain_attrs or {}).get(terr)
                    purpose = (
                        surface_purpose(
                            bool(attrs.get("requires_elevation")),
                            bool(attrs.get("technical_surface")),
                        )
                        if attrs is not None
                        else None
                    )
                    rows.append(
                        (
                            cdist if cdist is not None else float("inf"),
                            terrain_names.get(terr, terr),
                            cmeta.get("name") or cand,
                            cdist,
                            purpose,
                        )
                    )
                    break
        rows.sort(key=lambda t: (t[0], t[1]))
        venues = tuple((tn, ln, d) for _s, tn, ln, d, _p in rows)
        # Purpose-grouped routing: keep the nearest carrier per purpose (rows are
        # nearest-first, so the first seen per purpose wins).
        by_purpose: dict[str, tuple[str, str, float | None]] = {}
        for _s, tn, ln, d, p in rows:
            if p is not None:
                by_purpose.setdefault(p, (tn, ln, d))
        if len(by_purpose) >= 2 and len({v[1] for v in by_purpose.values()}) >= 2:
            routes = tuple(
                (p, *by_purpose[p]) for p in _SURFACE_PURPOSE_ORDER if p in by_purpose
            )

    return replace(
        resolution,
        locale_name=name,
        locale_distance_km=dist,
        terrain_venues=venues,
        surface_routes=routes,
    )


def feasibility_line(
    resolution: TerrainResolution,
    *,
    discipline_name: str,
    exercise_names: dict[str, str] | None = None,
) -> str:
    """The full one-line guidance for a resolved discipline (dedicated block).

    `exercise_names` maps the strength-substitute ids to display names; only the
    STRENGTH tier consumes it (falls back to the id when a name is missing).
    """
    loc = resolution.locale_id
    loc_label = _venue_label(
        resolution.locale_name, loc, resolution.locale_distance_km
    )
    tier = resolution.tier
    # The craft overlay (#586 WS-I) composes ahead of the terrain detail. A SWAP
    # prepends "you own <craft> — train as <swap-to discipline>" and the body
    # describes that swapped-to surface. A PROXY keeps the sport but notes you're
    # riding a different craft you own on the real terrain. A craft STRENGTH
    # terminal supplies its own reason in place of the terrain one.
    craft_prefix = ""
    if resolution.craft_tier == "swap":
        owned = (resolution.owned_craft or "your craft").replace("_", " ")
        swap_to = resolution.craft_swap_to_name or "a craft you own"
        craft_prefix = (
            f"you own a {owned}, not the gear for it — train this allocation as "
            f"{swap_to}. "
        )
    elif resolution.craft_tier == "proxy":
        owned = (resolution.owned_craft or "a craft you own").replace("_", " ")
        craft_prefix = (
            f"you don't own this discipline's craft, but your {owned} can ride the "
            "required terrain — use it there. "
        )
    if tier == "strength":
        names = ", ".join(
            (exercise_names or {}).get(ex, ex)
            for ex in resolution.substitute_exercise_ids
        ) or "the discipline's mapped strength pool"
        reason = (
            f"you own no {resolution.craft_kind or 'craft'} for this discipline"
            if resolution.craft_tier == "strength"
            else "no terrain, proxy, or machine in your locales"
        )
        return (
            f"- {discipline_name}: {reason} — substitute a STRENGTH session "
            f"targeting this discipline's demands at {loc_label} from: {names}. "
            "Keep the target hours; compose as strength."
        )
    if tier == "exact":
        if resolution.surface_routes:
            # Surface-specific routing (#624): each session purpose mapped to the
            # nearest venue carrying the surface that trains it, so the synthesizer
            # sends long/easy aerobic to flat-groomed and hill work to the hills
            # rather than collapsing every session onto the nearest surface.
            routing = "; ".join(
                f"{purpose} on {_venue_label(ln, None, d)} ({tn})"
                for purpose, tn, ln, d in resolution.surface_routes
            )
            body = (
                f"real terrain in your saved locales, routed by session purpose — "
                f"{routing}. Match each session to the surface its purpose calls for; "
                "do not collapse every session onto the nearest one. Train at these "
                "named locales only; never name or suggest a location not in this list."
            )
        elif resolution.terrain_venues:
            # Deterministic venue menu (#624): every real nearby surface + where,
            # so the synthesizer can't claim 'none nearby' or invent a farther one.
            menu = "; ".join(
                f"{tn} at {_venue_label(ln, None, d)}"
                for tn, ln, d in resolution.terrain_venues
            )
            body = (
                f"real terrain in your saved locales — {menu}. Train at these named "
                "locales only; never name or suggest a location not in this list."
            )
        else:
            body = (
                f"real terrain available at {loc_label} ({resolution.terrain_id}) — "
                "train it for real there."
            )
    elif tier == "proxy" and resolution.proxy_fidelity is None:
        # Craft-alt (#586 WS-I tier 2): own the craft, ride a substitute surface
        # it's compatible with (no gap-rule fidelity — the craft itself qualifies).
        owned = (resolution.owned_craft or "your craft").replace("_", " ")
        body = (
            f"no required terrain in your locales — ride your {owned} on the "
            f"available surface ({resolution.terrain_id}) at {loc_label}. Compose "
            "for that surface."
        )
    elif tier == "proxy":
        body = (
            f"no required terrain in your locales — train as the nearest surface "
            f"({resolution.terrain_id}, fidelity {resolution.proxy_fidelity:.2f}) "
            f"at {loc_label}. Compose for that surface."
        )
    elif tier == "indoor":
        body = (
            f"no outdoor terrain in your locales — train indoors on the "
            f"{resolution.machine} at {loc_label}."
        )
    else:  # reallocate
        body = (
            "infeasible anywhere in your locale cluster — do NOT prescribe this "
            "session; reallocate its time to feasible disciplines."
        )
    return f"- {discipline_name}: {craft_prefix}{body}"


def grid_annotation(resolution: TerrainResolution) -> str:
    """The short inline session-grid tag, or '' for tiers that don't change the
    session kind/placement (exact/proxy/indoor read the same count, just composed
    differently — the dedicated block carries that). Strength/reallocate change
    what the count MEANS, so they get an unmissable inline flag. The craft axis
    (#540 2c.2c) checks first: a SWAP changes the SPORT (compose as a different
    craft) even on an exact-terrain tier, and a craft STRENGTH terminal flags the
    real reason (no craft, not no terrain)."""
    if resolution.craft_tier == "swap":
        owned = (resolution.owned_craft or "craft").replace("_", " ")
        swap_to = resolution.craft_swap_to_name or "a craft you own"
        return (
            f" [CRAFT-SWAP: own a {owned} — compose as {swap_to}, NOT as-prescribed]"
        )
    if resolution.craft_tier == "strength":
        return (
            f" [NO CRAFT: you own no {resolution.craft_kind or 'craft'} — prescribe "
            "as a STRENGTH substitution, NOT a cardio session]"
        )
    if resolution.tier == "strength":
        return (
            " [TERRAIN-INFEASIBLE: no terrain/machine in your locales — prescribe "
            "as a STRENGTH substitution, NOT a cardio session]"
        )
    if resolution.tier == "reallocate":
        return (
            " [TERRAIN-INFEASIBLE: cannot be done anywhere in your cluster — "
            "reallocate this time, do NOT prescribe]"
        )
    return ""


# ─── Event Windows Slice 1 (#581 WS-H) — date-segmented subtractive overlay ───
# An event window is a date-bounded period where the athlete's training
# environment differs from the default home cluster. Slice 1 covers the two
# SUBTRACTIVE home overrides — `indoor_only` (home cluster minus all outdoor
# terrain) and `locale_unavailable(L)` (home cluster minus one locale). The
# resolution model is unchanged (Andy 2026-06-14): the EXACT→…→reallocate
# cascade above, just run against a reduced `(terrain, equipment)` input for a
# date range. The only new element here is the time dimension — cutting the plan
# span into atomic date sub-ranges at window boundaries so the orchestrator can
# run the existing cascade once per distinct reduced environment. (`away` — a
# DIFFERENT additive environment — is Slice 2, a third override_type.)


@dataclass(frozen=True)
class EventWindowOverride:
    """One override active over a date-segment. `unavailable_locale` is the
    `locale_profiles.locale` slug for `locale_unavailable`; `away_locale` is the
    destination slug (the cluster ANCHOR) for `away` (Slice 2). The first two
    types SUBTRACT from the home cluster; `away` REPLACES it with the
    destination's own radius cluster."""

    override_type: Literal[
        "indoor_only", "locale_unavailable", "away", "reduced_volume", "no_training"
    ]
    unavailable_locale: str | None = None
    away_locale: str | None = None
    # Slice 4 (#581 WS-H) — gear brought to this `away` window (the (c) surface);
    # unioned with the standing gear↔locale set for the destination cluster to
    # form the away segment's `owned_crafts`. Empty on non-away overrides. #884
    # slice 6c-1 — renamed `brought_craft`→`brought_gear` (legacy-craft retirement).
    brought_gear: tuple[str, ...] = ()
    # Slice 6 (#593) — retained capacity fraction for a `reduced_volume` override
    # (0 < pct < 1). None on every other type; `no_training` is the discrete 0%
    # type. Volume overrides change capacity, not feasibility — they carry no
    # terrain/locale subtraction (`_reduced_env` ignores them).
    volume_pct: float | None = None


@dataclass(frozen=True)
class EventWindowSegment:
    """An atomic date sub-range of the plan span whose environment differs from
    the home cluster, plus the per-discipline resolutions the window CHANGES.
    `resolutions` holds only the disciplines whose reduced/replacement-env
    routing differs from the home resolution — the set the synthesis overlay
    renders (an empty change-set means the window is a no-op for this athlete's
    disciplines and the segment is not emitted).

    `away_feasibility` (Slice 2) is the FULL away-environment resolution
    (`discipline -> TerrainResolution`), set only on `away` segments. The overlay
    renders the terse `resolutions` diff; the session grid needs the complete map
    to count a fully-away week against the destination (counts-follow-away,
    spec §4.1). None on subtractive segments.

    `assumed_baseline_category` (Slice 3 / F8) is the display label of the
    category equipment baseline the destination ASSUMED — set only on an `away`
    segment whose destination is cold (no logged equipment/terrain). It drives
    the overlay's "log actuals on arrival" note (Trigger-#1 wording); None
    whenever the destination has logged data or its category has no baseline."""

    start_date: date
    end_date: date
    overrides: tuple[EventWindowOverride, ...]
    resolutions: dict[str, TerrainResolution]
    away_feasibility: dict[str, TerrainResolution] | None = None
    assumed_baseline_category: str | None = None
    # #884 slice 6 (per-segment 2C re-resolve, PR-2) — the destination's
    # `toggle_off_for_discipline` 2C flags as `(discipline_name, gear_label)`
    # pairs: disciplines the athlete can't do at this away destination because the
    # gear that unlocks them is neither brought nor kept there. Set only on `away`
    # segments (None elsewhere); the overlay renders them so the synthesizer
    # doesn't program those disciplines for these dates.
    away_toggle_flags: tuple[tuple[str, str], ...] | None = None
    # Slice 6 (#593) — the segment's net VOLUME effect, computed from its active
    # volume overrides: 0.0 when any `no_training` covers it (day zeroed + dropped
    # from the placement pool), else the smallest `reduced_volume` fraction, else
    # None (no volume effect). The grid scales this segment's days' target hours
    # by it; the overlay renders the in-transit directive. A segment may carry
    # BOTH a feasibility change (`resolutions`) and `volume_pct` (union on the
    # same dates).
    volume_pct: float | None = None


def segment_window_boundaries(
    plan_start: date,
    plan_end: date,
    windows: list[tuple[date, date, EventWindowOverride]],
) -> list[tuple[date, date, tuple[EventWindowOverride, ...]]]:
    """Cut `[plan_start, plan_end]` (inclusive) into atomic date sub-ranges at
    every window boundary. Each returned sub-range carries the tuple of overrides
    active across ALL its days (overlapping windows → union of subtractions per
    §8); home-only sub-ranges (no active override) are dropped. Pure.

    Because every window start/end is a cut point, a window either fully covers
    or doesn't touch any given sub-range — so the active set is unambiguous.
    Overrides are emitted in a deterministic order (type, then locale)."""
    if plan_end < plan_start or not windows:
        return []
    clamped: list[tuple[date, date, EventWindowOverride]] = []
    for start, end, override in windows:
        cs, ce = max(start, plan_start), min(end, plan_end)
        if cs <= ce:
            clamped.append((cs, ce, override))
    if not clamped:
        return []
    one = timedelta(days=1)
    cuts = {plan_start, plan_end + one}
    for start, end, _ in clamped:
        cuts.add(start)
        cuts.add(end + one)
    points = sorted(c for c in cuts if plan_start <= c <= plan_end + one)
    segments: list[tuple[date, date, tuple[EventWindowOverride, ...]]] = []
    for seg_start, nxt in zip(points, points[1:]):
        seg_end = nxt - one
        if seg_end < seg_start:
            continue
        active = tuple(
            sorted(
                (ov for (s, e, ov) in clamped if s <= seg_start and e >= seg_end),
                key=lambda o: (o.override_type, o.unavailable_locale or ""),
            )
        )
        if active:
            segments.append((seg_start, seg_end, active))
    return segments


__all__ = [
    "TerrainResolution",
    "resolve_terrain_feasibility",
    "resolve_craft_terrain_feasibility",
    "required_terrains",
    "indoor_machines",
    "surface_purpose",
    "feasibility_line",
    "grid_annotation",
    "EventWindowOverride",
    "EventWindowSegment",
    "segment_window_boundaries",
]
