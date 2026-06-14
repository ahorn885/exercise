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

from dataclasses import dataclass, field
from typing import Literal

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
        locale_order: cluster locale ids, deterministic (home first). The first
            satisfying locale wins at each tier — a stand-in for nearest until a
            haversine sort is wired (mirrors `locale_assign`'s ordering choice).
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


# ─── Unified craft/terrain cascade (#586 WS-I, design §3) ────────────────────
# Craft disciplines (modality `group_kind ∈ {bike, paddle}`) walk ONE ordered
# cascade that composes craft ownership with terrain — replacing the old
# two-non-composing-axes split (a craft ladder that short-circuited ahead of
# terrain, so a craftless athlete with a trainer was sent to STRENGTH instead of
# the INDOOR machine they own). Non-craft disciplines (foot/swim/climb) keep the
# terrain-only `resolve_terrain_feasibility` cascade untouched.
#
# For each owned craft in priority order (the discipline's own craft first, then
# same-`group_kind` proxy crafts) a terrain sub-check runs — can the craft ride a
# required terrain that's in-cluster? then any terrain it's compatible with? —
# before falling through to indoor → strength → reallocate. "Craftless" is not a
# special branch: tiers 1–4 simply all miss and the walk lands on INDOOR (tier 5).
# Which terrains a craft can be ridden on is read explicitly from
# `layer0.craft_terrain_compatibility` (design §4) — NOT derived from the
# discipline graph, so a road bike and a gravel bike (both aliasing road/XC
# disciplines) differ on singletrack.
_CRAFT_GROUP_KINDS = frozenset({"bike", "paddle"})


def resolve_craft_terrain_feasibility(
    discipline_id: str,
    *,
    owned_crafts: list[str],
    craft_disciplines: dict[str, list[str]],
    craft_group_kind: dict[str, str],
    discipline_groups: dict[str, list[str]],
    group_kind: dict[str, str],
    craft_terrain: dict[str, set[str]],
    locale_order: list[str],
    cluster_terrain_by_locale: dict[str, set[str]],
    cluster_equipment_by_locale: dict[str, set[str]],
    discipline_exercise_ids: list[str],
    discipline_names: dict[str, str] | None = None,
) -> TerrainResolution | None:
    """The unified craft/terrain cascade for one craft discipline (design §3).

    Pure. Returns None when the discipline carries no craft (its modality group's
    `group_kind` is not bike/paddle) — the caller runs the terrain-only cascade
    instead. Otherwise walks the 7-tier cascade (first match wins):

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
    `{craft_slug: {TRN-xxx, ...}}` from `layer0.craft_terrain_compatibility`.
    """
    my_groups = set(discipline_groups.get(discipline_id, []))
    my_kinds = {group_kind[g] for g in my_groups if g in group_kind}
    target_kind = next((k for k in sorted(my_kinds) if k in _CRAFT_GROUP_KINDS), None)
    if target_kind is None:
        return None  # non-craft discipline — caller uses the terrain-only cascade

    required = required_terrains(discipline_id)
    same_kind = [c for c in sorted(set(owned_crafts)) if craft_group_kind.get(c) == target_kind]

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
            f"targeting this discipline's demands at \"{loc}\" from: {names}. "
            "Keep the target hours; compose as strength."
        )
    if tier == "exact":
        body = (
            f"real terrain available at \"{loc}\" ({resolution.terrain_id}) — "
            "train it for real there."
        )
    elif tier == "proxy" and resolution.proxy_fidelity is None:
        # Craft-alt (#586 WS-I tier 2): own the craft, ride a substitute surface
        # it's compatible with (no gap-rule fidelity — the craft itself qualifies).
        owned = (resolution.owned_craft or "your craft").replace("_", " ")
        body = (
            f"no required terrain in your locales — ride your {owned} on the "
            f"available surface ({resolution.terrain_id}) at \"{loc}\". Compose "
            "for that surface."
        )
    elif tier == "proxy":
        body = (
            f"no required terrain in your locales — train as the nearest surface "
            f"({resolution.terrain_id}, fidelity {resolution.proxy_fidelity:.2f}) "
            f"at \"{loc}\". Compose for that surface."
        )
    elif tier == "indoor":
        body = (
            f"no outdoor terrain in your locales — train indoors on the "
            f"{resolution.machine} at \"{loc}\"."
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


__all__ = [
    "TerrainResolution",
    "resolve_terrain_feasibility",
    "resolve_craft_terrain_feasibility",
    "required_terrains",
    "indoor_machines",
    "feasibility_line",
    "grid_annotation",
]
