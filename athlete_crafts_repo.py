"""athlete_crafts repository — Track 2 slice 2c.2b (#540).

Write + read side for the athlete's owned CRAFTS — cycling `bike_types_available`
+ paddling `paddle_craft_types`, the discipline-baseline fields that feed the
X1b.3b craft-substitution path: `_collect_athlete_crafts` →
`resolve_training_substitution` narrows substitution candidates to crafts that
share a modality group with the race discipline (via
`layer0.craft_discipline_aliases`).

The Layer 1 read path already exists (`layer1.builder._load_cycling_baseline` /
`_load_paddling_baseline` → `Layer1DisciplineBaselines`); this module adds the
profile-UI write side + the picker catalog. Mirrors
`athlete_discipline_weighting_repo`.

Convention: values are the snake_case craft slugs (`mountain_bike`, `kayak`)
that double as `craft_discipline_aliases.craft_name` keys — stored comma-
separated, the shape `layer1.builder._split_csv` reads. The capture form only
offers `BIKE_TYPES` / `PADDLE_CRAFT_TYPES`, and `CyclingBaseline` /
`PaddlingBaseline` re-assert the closed set downstream, so an unknown slug
can't silently leak into the alias lookup (the V4c silent-mismatch class).
"""
from __future__ import annotations

from athlete import BIKE_TYPES, CRAFT_LABELS, PADDLE_CRAFT_TYPES
from athlete_gear_repo import replace_owned_gear_for_kinds
from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend


class CraftSelectionError(ValueError):
    """A submitted craft slug is not in the closed BIKE_TYPES / PADDLE set."""


def load_craft_catalog() -> dict[str, list[dict]]:
    """The picker options grouped by discipline family — static, sourced from
    the `athlete` closed-enum constants + `CRAFT_LABELS`."""
    return {
        "cycling": [{"slug": s, "label": CRAFT_LABELS[s]} for s in BIKE_TYPES],
        "paddling": [{"slug": s, "label": CRAFT_LABELS[s]} for s in PADDLE_CRAFT_TYPES],
    }


def get_athlete_crafts(db, user_id: int) -> dict[str, list[str]]:
    """`{'bike_types': [...], 'paddle_crafts': [...]}` for the athlete; empty
    lists when the discipline-baseline row is absent or the column is null."""
    bike = db.execute(
        "SELECT bike_types_available FROM discipline_baseline_cycling "
        "WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    paddle = db.execute(
        "SELECT paddle_craft_types FROM discipline_baseline_paddling "
        "WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return {
        "bike_types": _split(bike["bike_types_available"] if bike else None),
        "paddle_crafts": _split(paddle["paddle_craft_types"] if paddle else None),
    }


def replace_athlete_crafts(
    db, user_id: int, *, bike_types: list[str], paddle_crafts: list[str],
    access_by_slug: dict[str, str] | None = None,
) -> None:
    """Replace the athlete's owned crafts (replace-all per family).

    `bike_types` / `paddle_crafts` are the SELECTED slugs; an empty list clears
    that family. Every slug must be in the matching closed enum, else
    `CraftSelectionError` is raised and nothing is written. Only the craft
    column on each discipline-baseline row is touched — sibling baseline fields
    (mtb_skill, longest_ride_*, …) are preserved. Caller commits.

    `access_by_slug` (#884 slice 6a) maps each selected slug → 'own' | 'access'
    for the unified "Your gear" surface; slugs absent from it default to 'own'
    (the onboarding own-only path). The baseline CSVs hold the full available set
    (own ∪ access) — they feed Layer 1 substitution, which doesn't distinguish
    access — while `athlete_gear` carries the per-craft access refinement.
    """
    bikes = _validate(bike_types, BIKE_TYPES, "bike type")
    paddles = _validate(paddle_crafts, PADDLE_CRAFT_TYPES, "paddle craft")
    db.execute(
        "INSERT INTO discipline_baseline_cycling "
        "  (user_id, bike_types_available, updated_at) VALUES (?, ?, NOW()) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "  bike_types_available = EXCLUDED.bike_types_available, updated_at = NOW()",
        (user_id, ",".join(bikes)),
    )
    db.execute(
        "INSERT INTO discipline_baseline_paddling "
        "  (user_id, paddle_craft_types, updated_at) VALUES (?, ?, NOW()) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "  paddle_craft_types = EXCLUDED.paddle_craft_types, updated_at = NOW()",
        (user_id, ",".join(paddles)),
    )
    # #884 slice 4 — close the read/write authority gap: keep the unified
    # athlete_gear store (the feasibility cascade's read source as of slice 4a) in
    # lockstep with the craft baselines. Crafts own the bike/paddle kinds; the
    # gear-toggle + swim surfaces write their own kinds (slices 4b / 6). Without
    # this, a craft edit landed on the baselines but the cascade read a stale
    # store between slice 4 and slice 6 (CARRY_FORWARD #884 attention item 1). The
    # baselines stay authoritative for the Layer 1 payload (builder reads them);
    # this is a forward-sync, not a move. Slugs are already enum-validated above
    # and BIKE_TYPES/PADDLE_CRAFT_TYPES ⊆ GEAR_REGISTRY, so no re-validation owed.
    # The per-craft access ('own' | 'access') lands here (the unified store is the
    # access authority — slice 6a); an unmapped slug defaults to 'own'. An out-of-
    # set access value is rejected by replace_owned_gear_for_kinds (nothing written).
    access = access_by_slug or {}
    replace_owned_gear_for_kinds(
        db,
        user_id,
        {slug: access.get(slug, "own") for slug in (*bikes, *paddles)},
        {"bike", "paddle"},
    )


def evict_layer1_on_crafts_change(db, user_id: int) -> None:
    """Owned crafts live in `Layer1DisciplineBaselines`, so a save invalidates
    every Layer 4 entry point + both Layer 3 wrappers per the Layer 1 eviction
    policy. Mirrors `evict_layer1_on_discipline_weighting_change`."""
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, "layer1")


def _split(value) -> list[str]:
    """Mirror of `layer1.builder._split_csv` for the read side."""
    if not value:
        return []
    return [tok.strip() for tok in value.split(",") if tok.strip()]


def _validate(values: list[str], allowed: tuple[str, ...], label: str) -> list[str]:
    """De-dupe + reject unknown slugs; emit in the enum's order for a stable
    stored string (deterministic Layer 1 hash)."""
    chosen = {v for v in values if v}
    unknown = chosen - set(allowed)
    if unknown:
        raise CraftSelectionError(f"unknown {label}(s): {', '.join(sorted(unknown))}")
    return [s for s in allowed if s in chosen]
