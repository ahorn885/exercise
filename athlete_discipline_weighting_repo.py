"""athlete_discipline_weighting repository — X2 (2026-06-10).

The write + read side for `athlete_discipline_weighting`, the per-athlete
discipline load split that Layer 2A consumes as `athlete_discipline_overrides`
(spec §5.4: athlete weight wins over the system race-time midpoint default).

The read path into the Layer 1 payload already exists
(`layer1.builder._load_discipline_weighting` →
`Layer1TrainingHistory.discipline_weighting`); this module adds the profile-UI
write side + the catalog the picker renders from.

Convention: `discipline_slug` stores the canonical `discipline_id` (`D-006`),
so the orchestrator unpack keys overrides directly with no slug→id mapping.
The per-user `weight_pct` sum-to-100 invariant is application-enforced (no DB
CHECK — intermediate multi-row states are valid); enforced at write time here
and re-asserted by the `Layer1TrainingHistory` model validator downstream.
"""
from __future__ import annotations

from discipline_display_names import discipline_display_name
from layer4.cache import Layer4Cache
from layer4.cache_invalidation import evict_on_layer_change
from layer4.cache_postgres import PostgresCacheBackend


def load_discipline_catalog(db) -> list[dict]:
    """All potential disciplines an athlete can weight — the distinct
    discipline set across every sport's bridge (current canonical mapping,
    `superseded_at IS NULL`), labeled with the curated pure-craft display
    name. Deduped by `discipline_id`; ordered by id for a stable picker.
    """
    cur = db.execute(
        """
        SELECT DISTINCT discipline_id, discipline_name
          FROM layer0.sport_discipline_bridge
         WHERE superseded_at IS NULL
         ORDER BY discipline_id
        """
    )
    seen: set[str] = set()
    out: list[dict] = []
    for r in cur.fetchall():
        did = r["discipline_id"]
        if did in seen:
            continue
        seen.add(did)
        out.append(
            {"id": did, "label": discipline_display_name(did, r["discipline_name"])}
        )
    return out


def get_discipline_weighting(db, user_id: int) -> dict[str, int]:
    """`{discipline_id: weight_pct}` for the athlete; `{}` if unset."""
    cur = db.execute(
        "SELECT discipline_slug, weight_pct FROM athlete_discipline_weighting "
        "WHERE user_id = ? ORDER BY discipline_slug",
        (user_id,),
    )
    return {r["discipline_slug"]: int(r["weight_pct"]) for r in cur.fetchall()}


class DisciplineWeightingError(ValueError):
    """Sum-to-100 / range invariant violated at write time."""


def replace_discipline_weighting(db, user_id: int, weights: dict[str, int]) -> None:
    """Replace the athlete's discipline weighting (all-or-nothing).

    `weights` maps `discipline_id -> weight_pct` for the SELECTED disciplines
    only (a 0 / absent discipline is unweighted). Empty dict clears the
    athlete's weighting (revert to system defaults). A non-empty set must sum
    to exactly 100 and every weight must be in 1..100 — otherwise
    `DisciplineWeightingError` is raised and nothing is written. Caller commits.
    """
    cleaned = {d: int(w) for d, w in weights.items() if int(w) > 0}
    if cleaned:
        if any(w > 100 for w in cleaned.values()):
            raise DisciplineWeightingError("each weight must be between 1 and 100")
        total = sum(cleaned.values())
        if total != 100:
            raise DisciplineWeightingError(
                f"discipline weights must sum to 100 (got {total})"
            )
    db.execute(
        "DELETE FROM athlete_discipline_weighting WHERE user_id = ?", (user_id,)
    )
    for did, pct in cleaned.items():
        db.execute(
            "INSERT INTO athlete_discipline_weighting "
            "  (user_id, discipline_slug, weight_pct, updated_at) "
            "VALUES (?, ?, ?, NOW())",
            (user_id, did, pct),
        )


def evict_layer1_on_discipline_weighting_change(db, user_id: int) -> None:
    """`discipline_weighting` lives in `Layer1TrainingHistory`, so a save
    invalidates every Layer 4 entry point + both Layer 3 wrappers per the
    Layer 1 eviction policy. Mirrors
    `athlete_skill_toggles_repo.evict_layer1_on_skill_toggle_change`."""
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    evict_on_layer_change(cache, user_id, "layer1")
