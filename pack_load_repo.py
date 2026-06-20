"""Structured §C pack-load-history capture — the athlete's load-carriage base.

One row per pack-weight tier the athlete currently trains at (`pack_weight_kg`),
with trailing-window summaries (`session_count_4wk`, `longest_session_hrs`),
free-text `terrain_type`, and optional `notes`. The Layer 1 builder
(`_load_pack_load_history`) reads these into `Layer1TrainingHistory.pack_load_history`;
Layer 3B summarizes them against the target race's `race_pack_weight_kg` to
gauge the load-carriage readiness gap. Mirrors the structured health-input
capture (`health_inputs_repo`): each add/delete is its own form, scoped on
`user_id`. Caller commits.
"""

from __future__ import annotations


def _clean_float(value, *, minimum: float | None = None):
    """Parse a float, or None when blank / non-numeric / below `minimum`."""
    try:
        f = float((value or "").strip())
    except (ValueError, TypeError, AttributeError):
        return None
    if minimum is not None and f < minimum:
        return None
    return f


def _clean_int(value, *, minimum: int | None = None):
    """Parse an int, or None when blank / non-numeric / below `minimum`."""
    try:
        i = int((value or "").strip())
    except (ValueError, TypeError, AttributeError):
        return None
    if minimum is not None and i < minimum:
        return None
    return i


def list_pack_loads(db, user_id) -> list[dict]:
    """The athlete's pack-load records, heaviest first."""
    if user_id is None:
        return []
    rows = db.execute(
        "SELECT id, pack_weight_kg, session_count_4wk, longest_session_hrs, "
        "       terrain_type, notes "
        "  FROM pack_load_history "
        " WHERE user_id = ? "
        " ORDER BY pack_weight_kg DESC, created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_pack_load(
    db, user_id, *, pack_weight_kg, session_count_4wk=None,
    longest_session_hrs=None, terrain_type: str | None = None,
    notes: str | None = None,
) -> bool:
    """Insert one pack-load record. Returns False (no insert) when
    `pack_weight_kg` is blank / non-numeric / negative — it's the only required
    field. The numeric companions are coerced (blank/junk → NULL). Caller
    commits."""
    weight = _clean_float(pack_weight_kg, minimum=0.0)
    if weight is None:
        return False
    db.execute(
        "INSERT INTO pack_load_history "
        "  (user_id, pack_weight_kg, session_count_4wk, longest_session_hrs, "
        "   terrain_type, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            weight,
            _clean_int(session_count_4wk, minimum=0),
            _clean_float(longest_session_hrs, minimum=0.0),
            (terrain_type or "").strip() or None,
            (notes or "").strip() or None,
        ),
    )
    return True


def delete_pack_load(db, user_id, pack_load_id) -> None:
    """Delete one pack-load record, scoped on `user_id` so a crafted POST can't
    reach another athlete's row. Caller commits."""
    db.execute(
        "DELETE FROM pack_load_history WHERE id = ? AND user_id = ?",
        (pack_load_id, user_id),
    )
