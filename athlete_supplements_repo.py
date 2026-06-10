"""Structured supplement capture (2E-6 §I.1).

Replaces the free-text `athlete_profile.supplement_protocol_notes` with
per-supplement records that soft-reference `layer0.supplement_vocabulary`
(the ETL-owned Layer 0 reference table — 25 seed entries). These records are
the structured input the Layer 2E supplement_integration de-stub
(recommendation + contraindication engine) consumes next; for now this module
just powers capture on the profile.

`canonical_name` + `category` are denormalized onto each record so the profile
list renders without a cross-schema join back to the vocab.
"""

from __future__ import annotations

from typing import Any


def load_supplement_vocab(db) -> list[dict]:
    """Active `layer0.supplement_vocabulary` rows for the add-supplement
    picker, ordered by category then name.

    Best-effort: the vocab is ETL-owned and lives in the `layer0` schema, which
    may be absent in a fresh dev DB. A missing table (or any read fault) yields
    an empty list rather than breaking the profile page — the picker simply
    renders empty.
    """
    try:
        rows = db.execute(
            "SELECT supplement_id, canonical_name, category, typical_dose, "
            "       primary_effect "
            "  FROM layer0.supplement_vocabulary "
            " WHERE superseded_at IS NULL "
            " ORDER BY category, canonical_name"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001 — advisory; never break the page
        print(f"load_supplement_vocab failed (non-fatal): {exc}")
        return []


def vocab_index(db) -> dict[str, dict]:
    """`supplement_id` -> vocab row, for validating + denormalizing a posted
    selection so a crafted POST can't store an unknown id or a spoofed name."""
    return {r["supplement_id"]: r for r in load_supplement_vocab(db)}


def list_athlete_supplements(db, user_id) -> list[dict]:
    """The athlete's structured supplement records, oldest first."""
    if user_id is None:
        return []
    rows = db.execute(
        "SELECT id, supplement_id, canonical_name, category, dose, timing, notes "
        "  FROM athlete_supplements WHERE user_id = ? "
        " ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_athlete_supplement(
    db, user_id, *, supplement_id: str, canonical_name: str,
    category: str | None, dose: str | None, timing: str | None,
    notes: str | None,
) -> None:
    """Insert one structured record. Caller resolves `canonical_name`/`category`
    from the vocab index (don't trust client-supplied display fields). Caller
    commits."""
    db.execute(
        "INSERT INTO athlete_supplements "
        "  (user_id, supplement_id, canonical_name, category, dose, timing, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, supplement_id, canonical_name, category, dose, timing, notes),
    )


def delete_athlete_supplement(db, user_id, supp_id) -> None:
    """Delete one record, scoped on `user_id` so a crafted POST can't reach
    another athlete's row. Caller commits."""
    db.execute(
        "DELETE FROM athlete_supplements WHERE id = ? AND user_id = ?",
        (supp_id, user_id),
    )
