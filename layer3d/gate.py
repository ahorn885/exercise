"""Layer 3D — HITL aggregation + gate (query/orchestration, no LLM).

Per `aidstation-sources/specs/Layer3D_Spec.md`. A deterministic node that sits
between Layer 3B and Layer 4: it collects the human-review items the upstream
nodes already emit (and that were, until now, produced and silently discarded)
into one typed `GateItem` list, applies the athlete's prior acknowledge/revise
resolutions, and computes a `gate_status` that gates Layer 4 synthesis.

**Slice 1.** Aggregation of the already-emitted upstream items (2A
`prompt_required` / `unresolved_flags`, 2D `hitl_items`, 2E `hitl_items` +
`supplement_integration.contraindication_hitl_items`, 3B `hitl_surface`) +
severity normalization (§5.1) + the resolution/status rules (§6.3) + the
gate-status computation (§5 step 6).

**Slice 2 (#214).** The two pre-synthesis feasibility detectors:
`detect_injury_pool_empty` (§5.2 — injury exclusions empty the strength pool →
blocker) and `detect_schedule_volume_under_target` (§5.3 — available hours below
the phase band → warning). Layer 4 keeps a defensive
`Layer4ShapeInfeasibleError` raise (`layer4.per_phase.assert_strength_pool_feasible`)
for the same injury condition. The §5.2 "only cardio modality banned" sub-case
and the 3C source remain deferred (no contract change when they land — §13).

The node is a **pure function of its inputs** (no clock, no RNG, no DB access)
per the Control_Spec §5/§6 query-node contract. `evaluated_at` is stamped by the
caller on persist; `GateResolution.resolved_at` is supplied by the route that
recorded the athlete's choice.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from layer4.context import (
    Layer2APayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3BPayload,
)

logger = logging.getLogger(__name__)

Severity = Literal["blocker", "warning", "informational"]
GateStatus = Literal["green", "needs_review", "blocked"]
GateItemStatus = Literal["pending", "acknowledged", "revised"]
GateSource = Literal["2A", "2D", "2E", "3B", "3C", "3D_feasibility"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer3DGateError(Exception):
    """Fail-fast precondition error (§4). Mirrors Layer 4's §4 raise shape so the
    gate fails the same way synthesis would on the same bad inputs, one step
    earlier and cheaper."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class Layer3DGateBlocked(Exception):
    """Orchestration signal: the gate is non-green, so the plan must be parked
    for athlete review instead of advancing to Layer 4 synthesis. Carries the
    evaluated `Layer3DGate` so the caller can persist it + flip the row to
    `needs_review`. Not a failure — a normal pre-synthesis stop (§11)."""

    def __init__(self, gate: "Layer3DGate") -> None:
        self.gate = gate
        super().__init__(
            f"Layer 3D gate is {gate.gate_status}; plan parked for review "
            f"({len(gate.items)} item(s))"
        )


# ─── Payload schema (§6) ─────────────────────────────────────────────────────


class GateResolution(_Base):
    """The athlete's resolution of a single item (§6.3). `resolved_at` is stamped
    by the route that records the choice, not by the pure gate function."""

    kind: Literal["acknowledged", "revised"]
    reasoning: str | None = None  # optional athlete note; only for 'acknowledged'
    resolved_at: datetime


class GateItem(_Base):
    item_key: str
    source: GateSource
    source_item_id: str | None = None
    severity: Severity
    title: str
    message: str
    resolution_options: list[str] = Field(default_factory=list)
    revise_target: str | None = None
    can_acknowledge: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    status: GateItemStatus = "pending"
    resolution: GateResolution | None = None


class Layer3DGate(_Base):
    user_id: int
    plan_version_id: int
    gate_status: GateStatus
    items: list[GateItem] = Field(default_factory=list)
    evaluated_against: dict[str, str] = Field(default_factory=dict)
    # Stamped by the caller on persist (§6.1), not inside the pure function.
    evaluated_at: datetime | None = None


# ─── item_key derivation (§6.4) ──────────────────────────────────────────────


def make_item_key(source: str, source_item_id: str | None, discriminator: str) -> str:
    """Stable per-item identity across re-evaluation rounds (§6.4):
    `sha256(source | source_item_id | discriminator)[:16]`. The same finding
    keeps the same key, so a round-1 resolution still applies after an unrelated
    round-2 revise."""
    raw = f"{source}|{source_item_id or ''}|{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ─── Aggregation: one mapper per source (§5 step 3 / §5.1) ───────────────────


def map_2a_items(payload: Layer2APayload) -> list[GateItem]:
    """2A: `prompt_required` disciplines (→ warning) + `unresolved_flags`
    (`error` → blocker, `warning` → warning). §5.1."""
    items: list[GateItem] = []
    for disc in payload.disciplines:
        if disc.inclusion != "prompt_required":
            continue
        items.append(
            GateItem(
                item_key=make_item_key("2A", disc.discipline_id, "inclusion"),
                source="2A",
                source_item_id=disc.discipline_id,
                severity="warning",
                title=f"Confirm discipline: {disc.discipline_name}",
                message=(
                    f"We weren't sure whether {disc.discipline_name} belongs in this "
                    f"plan. {disc.rationale} Confirm or drop it so the plan trains the "
                    "right mix."
                ),
                resolution_options=[
                    f"Include {disc.discipline_name}",
                    f"Drop {disc.discipline_name}",
                ],
                revise_target="profile.disciplines",
                can_acknowledge=True,
                evidence={"discipline_id": disc.discipline_id, "role": disc.role},
            )
        )
    for flag in payload.unresolved_flags:
        severity: Severity = "blocker" if flag.severity == "error" else "warning"
        suffix = (
            f" Did you mean '{flag.suggested_match}'?" if flag.suggested_match else ""
        )
        items.append(
            GateItem(
                item_key=make_item_key("2A", flag.raw_input, flag.severity),
                source="2A",
                source_item_id=flag.raw_input,
                severity=severity,
                title=f"Unrecognized input: {flag.raw_input}",
                message=(
                    f"We couldn't match '{flag.raw_input}' to a known discipline."
                    + suffix
                ),
                resolution_options=[],
                revise_target="profile.disciplines",
                can_acknowledge=severity != "blocker",
                evidence={"raw_input": flag.raw_input, "suggested_match": flag.suggested_match},
            )
        )
    return items


def map_2d_items(payload: Layer2DPayload) -> list[GateItem]:
    """2D: `hitl_items` — `block` → blocker, `warn` → warning. §5.1.
    `revise_target` points at the §B injury record."""
    items: list[GateItem] = []
    for hi in payload.hitl_items:
        severity: Severity = "blocker" if hi.severity == "block" else "warning"
        items.append(
            GateItem(
                item_key=make_item_key("2D", hi.hitl_type, hi.discipline_id or ""),
                source="2D",
                source_item_id=hi.hitl_type,
                severity=severity,
                title=hi.hitl_type.replace("_", " ").title(),
                message=hi.message,
                resolution_options=list(hi.suggested_resolutions),
                revise_target="profile.injuries",
                can_acknowledge=severity != "blocker",
                evidence={
                    "hitl_type": hi.hitl_type,
                    "discipline_id": hi.discipline_id,
                },
            )
        )
    return items


def map_2e_items(payload: Layer2EPayload) -> list[GateItem]:
    """2E: `hitl_items` + `supplement_integration.contraindication_hitl_items`.
    `block_level == 'block'` → blocker, else warning (§5.1). A contraindication
    item that duplicates a `hitl_items` entry de-dups by `item_key` (§9)."""
    items: list[GateItem] = []
    combined = list(payload.hitl_items) + list(
        payload.supplement_integration.contraindication_hitl_items
    )
    for hi in combined:
        severity: Severity = "blocker" if hi.block_level == "block" else "warning"
        items.append(
            GateItem(
                item_key=make_item_key("2E", hi.item_id, str(hi.gate_number)),
                source="2E",
                source_item_id=hi.item_id,
                severity=severity,
                title=hi.item_id.replace("_", " ").title(),
                message=hi.rationale_for_athlete,
                resolution_options=list(hi.resolution_options),
                revise_target="profile.nutrition",
                can_acknowledge=severity != "blocker",
                evidence={
                    "item_id": hi.item_id,
                    "gate_number": hi.gate_number,
                    "affected_supplement_id": hi.affected_supplement_id,
                    "affected_event_id": hi.affected_event_id,
                    "affected_condition_category": hi.affected_condition_category,
                },
            )
        )
    return items


def map_3b_items(payload: Layer3BPayload) -> list[GateItem]:
    """3B: `hitl_surface` — severity carried verbatim (`blocker` / `warning` /
    `informational`). 3B already sets `acknowledge_option = None` for blockers,
    so `can_acknowledge` follows that contract. §5.1."""
    items: list[GateItem] = []
    for hi in payload.hitl_surface:
        items.append(
            GateItem(
                item_key=make_item_key("3B", hi.item_label, ""),
                source="3B",
                source_item_id=hi.item_label,
                severity=hi.severity,
                title=hi.item_label.replace("_", " ").title(),
                message=hi.description,
                resolution_options=[hi.recommended_action],
                revise_target=hi.revise_target,
                can_acknowledge=hi.acknowledge_option is not None,
                evidence={"revise_option": hi.revise_option},
            )
        )
    return items


# ─── Feasibility detectors (§5.2 / §5.3) ─────────────────────────────────────

# v1 strength-pool floor (Andy 2026-06-21): a workable strength session needs ≥3
# distinct exercises; a post-exclusion pool below this can't fill one. Mirrors
# `layer4.per_phase._STRENGTH_POOL_FLOOR` (the defensive-raise side) — keep synced.
_STRENGTH_POOL_FLOOR = 3


def detect_injury_pool_empty(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    *,
    floor: int = _STRENGTH_POOL_FLOOR,
) -> list[GateItem]:
    """§5.2 injury-empties-the-pool blocker — the one #214 detector that survives
    as a hard stop. Strength is prescribed in every phase (Layer 4's
    `_STRENGTH_SESSIONS_PER_WEEK` is Base/Build 2, Peak/Taper 1 — never 0), so
    every plan needs a usable strength pool; there is no "this plan skips
    strength" case in the implemented periodization, which is why this fires
    plan-globally rather than per-phase.

    The pool checked is `compute_feasible_pool_ids` — the resolved strength pool
    Layer 4 actually synthesizes from (strength-type `exercises_resolved` across
    locales, minus tier-0 infeasible, minus 2D exclusions) — NOT the raw 2C
    `effective_pool` the spec names loosely, so the gate's verdict matches what
    synthesis can build. The blocker fires only when 2D exclusions are what
    emptied it: viable pre-injury (≥ floor), sub-floor after. A pool already
    sub-floor pre-injury is a sport/equipment limit (the synthesizer reverts to a
    free-string schema), not an injury — out of #214 scope.

    The §5.2 "only cardio modality banned" sub-case is NOT implemented: the 2D
    payload carries no per-discipline modality-ban signal (`DisciplineRisk` has a
    risk *grade* + suggested substitutes, never an "untrainable" verdict), so
    detecting it would need a new 2D field — tracked as a follow-up, not invented
    from a fragile heuristic here.

    `compute_feasible_pool_ids` is imported lazily so this pure query node doesn't
    pull the synthesis package at import time (mirrors the orchestrator's lazy
    gate import)."""
    from layer4.per_phase import compute_feasible_pool_ids

    pool_after = set(compute_feasible_pool_ids(layer2c_payloads, layer2d_payload))
    if len(pool_after) >= floor:
        return []
    pool_before = set(compute_feasible_pool_ids(layer2c_payloads, None))
    if len(pool_before) < floor:
        return []  # never viable pre-injury → not an injury emptying (out of scope)
    emptying_ids = sorted(pool_before - pool_after)
    return [
        GateItem(
            item_key=make_item_key("3D_feasibility", "injury_pool_empty", "strength_pool"),
            source="3D_feasibility",
            source_item_id="injury_pool_empty",
            severity="blocker",
            title="Injuries leave too few usable strength exercises",
            message=(
                f"After your injury exclusions, only {len(pool_after)} strength "
                f"exercise(s) remain usable — a workable strength session needs at "
                f"least {floor}. The plan can't build safe strength work from this "
                f"pool. Relax an injury input or drop a discipline that forces the "
                f"excluded movements."
            ),
            resolution_options=[],
            revise_target="profile.injuries",
            can_acknowledge=False,
            evidence={
                "usable_strength_count": len(pool_after),
                "pre_injury_strength_count": len(pool_before),
                "floor": floor,
                "excluded_exercise_ids": emptying_ids,
            },
        )
    ]


def detect_schedule_volume_under_target(
    phase_structure: Any,
    layer2a_payload: Layer2APayload,
    layer1_payload: dict[str, Any],
) -> GateItem | None:
    """§5.3 schedule-volume-under-target warning. Compares the athlete's bounded
    available weekly hours (`weekly_capacity_hours` — Σ enabled §K windows, capped
    by `weekly_hours_target`) against each phase's framework total LOW band
    (`Layer2APayload.weekly_total_hours_by_phase[phase]` — the `(low, high)` the
    block targets, exactly what the §5.3 message renders). Emits ONE warning for
    the worst (largest-shortfall) phase; the rest ride `evidence` (§9: no
    per-phase spam).

    Never blocks, never raises — Layer 4 already clamps prescribed volume to
    capacity (`phase_volume_bands_hours` `min(capacity, band)`), so the plan is
    built to the hours the athlete has; the gate's only job is to make that trim
    non-silent. `weekly_capacity_hours` is imported lazily (pure-node hygiene).

    `phase_structure` is a `layer4.payload.PhaseStructure` (typed `Any` to keep
    this query node free of a synthesis-side import)."""
    from layer4.validator import weekly_capacity_hours

    available = weekly_capacity_hours(layer1_payload)
    if available is None:
        return None  # no §K availability / hours target → nothing to compare
    totals = layer2a_payload.weekly_total_hours_by_phase or {}
    under: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for ph in phase_structure.phases:
        if ph.phase_name in seen:
            continue
        band = totals.get(ph.phase_name)
        if not band:
            continue
        low, high = float(band[0]), float(band[1])
        if available < low:
            under.append((ph.phase_name, low, high))
            seen.add(ph.phase_name)
    if not under:
        return None
    worst_phase, worst_low, worst_high = max(under, key=lambda t: t[1] - available)
    return GateItem(
        item_key=make_item_key("3D_feasibility", "schedule_volume_under_target", "schedule"),
        source="3D_feasibility",
        source_item_id="schedule_volume_under_target",
        severity="warning",
        title="Your schedule is below the plan's target hours",
        message=(
            f"Your schedule gives about {available:g} h/week; this block targets "
            f"{worst_low:g}–{worst_high:g} h. The plan will be built to the time you "
            f"have, but expect it to under-prepare you for the demand — add training "
            f"days or a longer runway if you can."
        ),
        resolution_options=["Add training days", "Extend the timeline"],
        revise_target="profile.availability",
        can_acknowledge=True,
        evidence={
            "available_hours": available,
            "worst_phase": worst_phase,
            "phases_under_target": [
                {"phase": p, "target_low": lo, "target_high": hi} for p, lo, hi in under
            ],
        },
    )


# ─── Resolution / status rules (§6.3) + gate-status (§5 step 6) ───────────────


def resolved_status(item: GateItem) -> GateItemStatus:
    """§6.3. No resolution → `pending`. `acknowledged` → `acknowledged` (only
    when the item is acknowledgeable; an acknowledge on a blocker is rejected at
    the route and defensively dropped to `pending` here). `revised` → `pending`
    when the item is still present (the edit didn't clear it — §9 "revise that
    doesn't fix"); a revise that *does* fix it simply makes the item disappear
    from re-aggregation, so it never reaches this function."""
    res = item.resolution
    if res is None:
        return "pending"
    if res.kind == "acknowledged":
        return "acknowledged" if item.can_acknowledge else "pending"
    # res.kind == 'revised' but the item re-surfaced → not actually fixed.
    return "pending"


def compute_gate_status(items: list[GateItem]) -> GateStatus:
    """§5 step 6. `green` when every item is resolved; `blocked` when any blocker
    is still pending; otherwise `needs_review`."""
    if all(it.status in ("acknowledged", "revised") for it in items):
        return "green"
    if any(it.severity == "blocker" and it.status == "pending" for it in items):
        return "blocked"
    return "needs_review"


# ─── Preconditions (§4) ──────────────────────────────────────────────────────


def _coherent_etl_version_set(
    layer2a_payload: Layer2APayload,
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3b_payload: Layer3BPayload,
) -> dict[str, str]:
    """The aggregation-source payloads must pin the same `etl_version_set` (§4
    `etl_version_set_mismatch`). Returns the coherent set.

    2C is intentionally excluded: it encodes the source table in the *value*
    (`{'0A': 'sports=v7', ...}`) rather than a bare version, so a literal
    dict-equality against the other nodes' canonical `{'0A': 'v7', ...}` shape
    would always (and wrongly) trip. 2C is also unused by the Slice 1
    aggregation — only the deferred §5.2/§5.3 feasibility detectors read it."""
    sets: list[tuple[str, dict[str, str]]] = [
        ("2A", layer2a_payload.etl_version_set),
        ("2D", layer2d_payload.etl_version_set),
        ("2E", layer2e_payload.etl_version_set),
        ("3B", layer3b_payload.etl_version_set),
    ]
    reference = sets[0][1]
    for name, evs in sets[1:]:
        if evs != reference:
            raise Layer3DGateError(
                "etl_version_set_mismatch",
                f"{sets[0][0]} pins {reference} but {name} pins {evs}",
            )
    return dict(reference)


# ─── Entry point (§3 / §5) ───────────────────────────────────────────────────


def evaluate_layer3d_gate(
    *,
    user_id: int,
    plan_version_id: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    layer2c_payloads: dict[str, Layer2CPayload] | None,
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3b_payload: Layer3BPayload | None,
    plan_start_date: Any = None,
    total_weeks: int | None = None,
    race_event_payload: Any = None,
    prior_resolutions: dict[str, GateResolution] | None = None,
) -> Layer3DGate:
    """Aggregate upstream HITL items, apply prior resolutions, and compute the
    gate status (§3 / §5). Pure + deterministic given inputs — no clock, no RNG,
    no DB access. The caller persists the returned `Layer3DGate` (stamping
    `evaluated_at`) and re-invokes on each resolution round.

    `plan_start_date` / `total_weeks` / `race_event_payload` are part of the §3
    contract for the §5.2/§5.3 feasibility detectors (next slice); they are
    accepted now so the signature is stable and unused until the detectors land.
    """
    # 1. Preconditions (§4) — fail-fast.
    if plan_version_id <= 0:
        raise Layer3DGateError("plan_version_id_unset", f"got {plan_version_id}")
    missing = [
        name
        for name, p in (
            ("2A", layer2a_payload),
            ("2C", layer2c_payloads),
            ("2D", layer2d_payload),
            ("2E", layer2e_payload),
            ("3B", layer3b_payload),
        )
        if p is None
    ]
    if missing:
        raise Layer3DGateError(
            "missing_upstream_payload", f"required payload(s) None: {', '.join(missing)}"
        )
    # mypy/readers: the missing-check above narrows these to non-None.
    assert layer2a_payload is not None
    assert layer2c_payloads is not None
    assert layer2d_payload is not None
    assert layer2e_payload is not None
    assert layer3b_payload is not None

    etl_version_set = _coherent_etl_version_set(
        layer2a_payload,
        layer2d_payload,
        layer2e_payload,
        layer3b_payload,
    )

    # 2-3. Aggregate: read each source's emitted items verbatim (§5 step 3).
    items: list[GateItem] = []
    items += map_2a_items(layer2a_payload)
    items += map_2d_items(layer2d_payload)
    items += map_2e_items(layer2e_payload)
    items += map_3b_items(layer3b_payload)
    # 3C deferred (§13). When built: items += map_3c_items(layer3c_payload)

    # 4. Feasibility detectors (§5.2/§5.3). The injury-pool blocker is plan-global
    #    (the strength pool isn't phase-scoped). The schedule-volume warning needs
    #    the phase structure, recomputed here from the same (3B, start_date,
    #    total_weeks) the orchestrator used (pure → matches); skipped when the
    #    caller didn't supply a start date (e.g. a non-plan-create probe).
    items += detect_injury_pool_empty(layer2c_payloads, layer2d_payload)
    if plan_start_date is not None:
        from layer4.phase_structure import phase_structure_from_3b

        phase_structure = phase_structure_from_3b(
            layer3b_payload, plan_start_date, total_weeks=total_weeks
        )
        vol_item = detect_schedule_volume_under_target(
            phase_structure, layer2a_payload, layer1_payload
        )
        if vol_item is not None:
            items.append(vol_item)

    # De-dup by item_key (§9: a 2E contraindication item that duplicates a
    # hitl_items entry surfaces once; also guards any accidental collision).
    deduped: dict[str, GateItem] = {}
    for it in items:
        deduped.setdefault(it.item_key, it)
    items = list(deduped.values())

    # Rule #15: trust the items list, not the `hitl_required` flag — but log the
    # inconsistency when a source claims HITL with no items (§9).
    for name, flag, count in (
        ("2A", layer2a_payload.hitl_required, len(map_2a_items(layer2a_payload))),
        ("2D", layer2d_payload.hitl_required, len(layer2d_payload.hitl_items)),
        ("2E", layer2e_payload.hitl_required, len(layer2e_payload.hitl_items)),
    ):
        if flag and count == 0:
            logger.warning(
                "layer3d: %s hitl_required=True but emitted 0 items "
                "(plan_version_id=%s); trusting the empty items list",
                name,
                plan_version_id,
            )

    # 5. Apply prior resolutions + recompute per-item status (§5 step 5 / §6.3).
    prior = prior_resolutions or {}
    for it in items:
        it.resolution = prior.get(it.item_key)
        it.status = resolved_status(it)

    # 6. Gate status (§5 step 6).
    gate_status = compute_gate_status(items)

    return Layer3DGate(
        user_id=user_id,
        plan_version_id=plan_version_id,
        gate_status=gate_status,
        items=items,
        evaluated_against=etl_version_set,
        evaluated_at=None,  # caller stamps on persist (§6.1)
    )
