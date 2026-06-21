"""Single-source strength catalog read from layer0 — the one canonical exercise
catalog — replacing the retired v1 `exercise_inventory` display reads (the
catalog-unification work; supersedes the #814 name↔EX-id bridge).

Keyed by the layer0 EX-id, the same id `current_rx.layer0_exercise_id` and
plan-gen already carry, so there is no name drift and no second hand-authored
catalog to fall out of sync.

Intentionally dropped from the v1 catalog (see the unification decision):
  * `discipline` (Bike/Foot/Water/Cross) — a *cardio* concept hand-stamped onto
    every lift; it never belonged on strength/mobility work, so we don't derive
    or carry it. The catalog is organized by its layer0-native attributes
    instead (`exercise_type` + the movement-pattern progression group).
  * `type` (Staple/Novel) — legacy curation, superseded by `exercise_type`.
  * `suggested_volume` — vestigial; plan-gen prescribes volume now.

`where_available` is *derived* from `equipment_required`: a bodyweight movement
(no required gear) resolves in every locale; a gear-bound movement resolves to
the home gym. Read-only; the canonical store is layer0.
"""

from __future__ import annotations

from layer0_progression import progression_pattern

# Resistance + athletic-development `exercise_type`s that belong on the strength
# Rx page — mirrors layer4.per_phase._STRENGTH_POOL_EXERCISE_TYPES (Andy-ratified
# 2026-06-17). Inlined (not imported) to keep this leaf module free of the heavy
# layer4 import graph; the set is stable. Cardio (Interval/Tempo, Aerobic/
# Endurance), pure skill (Technical/Skill), and recovery/mobility types are
# excluded — they are not strength prescriptions.
_STRENGTH_TYPES = frozenset({
    "strength", "power", "loaded carry", "plyometric", "isometric",
    "agility", "activation / primer", "balance / proprioception",
})

# Locale tokens an exercise needing no equipment is available at (mirrors the v1
# bodyweight `where_available` set). Gear-bound movements resolve to the home gym.
_ALL_LOCALES = "home,hotel,partner,airport"
_HOME_ONLY = "home"


def _is_strength_type(exercise_type) -> bool:
    return (exercise_type or "").strip().lower() in _STRENGTH_TYPES


def _derive_where_available(equipment_required) -> str:
    """Bodyweight (empty equipment_required) → available everywhere; any required
    gear → home gym only. The flat heuristic the v1 `where_available` encoded."""
    return _ALL_LOCALES if not equipment_required else _HOME_ONLY


def strength_catalog(db) -> list[dict]:
    """Active layer0 strength-type exercises as display rows, EX-id keyed.

    Each row: `layer0_exercise_id`, `exercise` (canonical layer0 name),
    `exercise_type`, `movement_pattern` (the rx progression group), and a derived
    `where_available`. Ordered by name for stable rendering.
    """
    rows = db.execute(
        "SELECT exercise_id, exercise_name, exercise_type, movement_patterns, "
        "equipment_required FROM layer0.exercises "
        "WHERE superseded_at IS NULL ORDER BY exercise_name"
    ).fetchall()
    catalog: list[dict] = []
    for r in rows:
        if not _is_strength_type(r["exercise_type"]):
            continue
        catalog.append({
            "layer0_exercise_id": r["exercise_id"],
            "exercise": r["exercise_name"],
            "exercise_type": r["exercise_type"],
            "movement_pattern": progression_pattern(list(r["movement_patterns"] or [])),
            "where_available": _derive_where_available(r["equipment_required"]),
        })
    return catalog


def strength_catalog_by_exid(db) -> dict[str, dict]:
    """`strength_catalog` indexed by EX-id, for enriching a `current_rx` row from
    its `layer0_exercise_id`."""
    return {c["layer0_exercise_id"]: c for c in strength_catalog(db)}
