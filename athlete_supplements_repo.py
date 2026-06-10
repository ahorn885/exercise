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


# Closed vocabularies for the structured frequency/timing selects (2E-6 §I.1).
# Ordered (value, label) pairs — `value` is the stored token, `label` the UI
# string. These are app-owned *capture* enums (how often / when an athlete takes
# something), distinct from the ETL-owned Layer 0 supplement catalog. Frequency
# and timing are orthogonal — e.g. creatine is "Daily" + "Post-exercise",
# caffeine is "As needed" + "Pre-exercise" — so they're two fields, not one.
SUPPLEMENT_FREQUENCIES: list[tuple[str, str]] = [
    ("daily", "Daily"),
    ("twice_daily", "Twice daily"),
    ("weekly_few", "A few times a week"),
    ("as_needed", "As needed"),
]
SUPPLEMENT_TIMINGS: list[tuple[str, str]] = [
    ("pre_exercise", "Pre-exercise"),
    ("during_exercise", "During exercise"),
    ("post_exercise", "Post-exercise"),
    ("morning", "Morning"),
    ("evening", "Evening / bedtime"),
    ("with_meals", "With meals"),
    ("anytime", "Anytime"),
]

# Token -> label, for rendering a stored record back to its display string.
FREQUENCY_LABELS: dict[str, str] = dict(SUPPLEMENT_FREQUENCIES)
TIMING_LABELS: dict[str, str] = dict(SUPPLEMENT_TIMINGS)


def clean_frequency(value: str | None) -> str | None:
    """Return the posted frequency only if it's in the closed vocab, else None —
    a tampered or blank POST stores NULL rather than a junk token."""
    v = (value or "").strip()
    return v if v in FREQUENCY_LABELS else None


def clean_timing(value: str | None) -> str | None:
    """Return the posted timing only if it's in the closed vocab, else None."""
    v = (value or "").strip()
    return v if v in TIMING_LABELS else None


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
        "SELECT id, supplement_id, canonical_name, category, dose, frequency, "
        "       timing, notes "
        "  FROM athlete_supplements WHERE user_id = ? "
        " ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_athlete_supplement(
    db, user_id, *, supplement_id: str, canonical_name: str,
    category: str | None, dose: str | None, frequency: str | None,
    timing: str | None, notes: str | None,
) -> None:
    """Insert one structured record. Caller resolves `canonical_name`/`category`
    from the vocab index (don't trust client-supplied display fields) and
    validates `frequency`/`timing` against the closed vocabs. Caller commits."""
    db.execute(
        "INSERT INTO athlete_supplements "
        "  (user_id, supplement_id, canonical_name, category, dose, frequency, "
        "   timing, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, supplement_id, canonical_name, category, dose, frequency,
         timing, notes),
    )


def delete_athlete_supplement(db, user_id, supp_id) -> None:
    """Delete one record, scoped on `user_id` so a crafted POST can't reach
    another athlete's row. Caller commits."""
    db.execute(
        "DELETE FROM athlete_supplements WHERE id = ? AND user_id = ?",
        (supp_id, user_id),
    )
