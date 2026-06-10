"""Layer 0 ETL — sport canon (curation layer for framework sports).

Background
----------
Disciplines have a code-side canon (`discipline_canon.py`) that curates the raw
xlsx rows at ETL time — renames, removals, merges. Framework **sports** had no
equivalent: they flowed straight from the Sports Framework workbook Sheet 1 into
`layer0.sports`, with no diff-reviewable place to express "remove this sport."

This module is that place. It mirrors the discipline canon: a small, code-
reviewed set of structural decisions applied at ETL time (the source xlsx is
never modified — same convention as `discipline_canon` / `sport_name_aliases`).
The app already reads sports only from the DB (`SELECT … FROM layer0.sports`),
never the xlsx — so curating what the ETL pulls is sufficient, and a re-run
re-applies the canon deterministically (the stale xlsx rows can't leak back).

Canon decisions captured: Andy, May 2026.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Sports removed from the canon entirely.
#   Modern Pentathlon / Biathlon -> dropped as supported sports (extremely
#     niche; their pentathlon/biathlon-only disciplines D-025 Fencing,
#     D-026 Laser Run, D-029 Rifle Shooting are removed in lockstep — see
#     discipline_canon.REMOVED_IDS). Andy, May 2026.
# Matching is on the framework `sport_name` exactly as it appears in
# `layer0.sports` (post newline-strip normalization done by extract_sports).
# ---------------------------------------------------------------------------
REMOVED_SPORTS: frozenset[str] = frozenset({"Modern Pentathlon", "Biathlon"})

# Structural home for future sport renames/merges (analogous to
# discipline_canon.ID_REMAP). Empty today — declared so the curation surface
# exists in one obvious place rather than being invented ad hoc later.
SPORT_NAME_REMAP: dict[str, str] = {}


def _canon_sport_name(name: str | None) -> str:
    """Normalize a raw sport name for canon matching (strip + collapse the
    embedded-newline variants that extract_sports also normalizes)."""
    return (name or "").replace("\n", " ").strip()


def is_removed_sport(sport_name: str | None) -> bool:
    """True if the (normalized) framework sport has been removed from the canon."""
    return _canon_sport_name(sport_name) in REMOVED_SPORTS


def filter_sport_rows(
    rows: list[dict],
    *,
    sport_field: str = "sport_name",
    dropped: list[dict] | None = None,
) -> list[dict]:
    """Drop rows belonging to a removed sport, from any sport-keyed table.

    Used on every sport-keyed extract in the ETL (`layer0.sports`,
    `sport_discipline_map`, `phase_load_allocation`, `phase_load_weekly_totals`,
    `team_formats`, `sport_exercise_map`, and the `sport_name_aliases`
    framework-sport targets). Dropped rows are appended to `dropped` if given,
    for surfacing in the ETL report.
    """
    out: list[dict] = []
    for row in rows:
        if is_removed_sport(row.get(sport_field)):
            if dropped is not None:
                dropped.append(row)
            continue
        out.append(row)
    return out
