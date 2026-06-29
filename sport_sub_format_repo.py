"""Layer-0 sport sub-format lookups (#254 / D-17, slice B).

`layer0.sport_sub_format_map` (migration 0033, slice A) maps each of the five
sub-format-parent sports (Triathlon, Skimo, Long Distance / Endurance Cycling,
Canoe / Kayak Marathon, Open Water Marathon Swimming) to its full
`phase_load_allocation.sport_name` sub-formats, with exactly one `is_default`
row per parent. A sport with no rows here is a single-format sport that needs
no sub-format resolution.

The Layer 4 orchestrator reads `default_sub_format` to compose the Layer 2A
`framework_sport` input (`sport_sub_format or default or parent`) so a bare
sub-format parent resolves to a real PLA `sport_name` instead of joining zero
phase-load bands (the silent no-volume-plan bug this issue closes). The
athlete-facing option list + default pre-selection (slice B2) read the same
table.

Schema reference: `etl/migrations/layer0/0033_sport_sub_format_map.sql`.
Design: `aidstation-sources/designs/Onboarding_SportSubFormat_D17_254_Design_v1.md`
(D2 — defaults are a Layer-0, data-driven fact).
"""

from __future__ import annotations


def default_sub_format(db, parent_sport: str | None) -> str | None:
    """Return the curated default `sub_format_sport` for a parent sport, or
    None when the parent has no `sport_sub_format_map` rows (a single-format
    sport — the orchestrator then falls back to the bare parent name).

    Reads the current canonical mapping (`superseded_at IS NULL`); runtime
    etl-version pinning is Layer 2A's concern, same as the bridge/PLA reads
    (`_framework_sport_choices`, `_disciplines_for_framework_sport`).
    """
    if not parent_sport:
        return None
    cur = db.execute(
        """
        SELECT sub_format_sport
          FROM layer0.sport_sub_format_map
         WHERE parent_sport = ?
           AND is_default = TRUE
           AND superseded_at IS NULL
         LIMIT 1
        """,
        (parent_sport,),
    )
    row = cur.fetchone()
    return row["sub_format_sport"] if row else None


def _option_dict(row) -> dict:
    """Shape one map row into the athlete-facing option the form + JSON blob
    read: the full PLA `sub_format_sport` (the submitted/stored value), the
    short `display_label` (the parenthetical, shown in the select), and the
    `is_default` flag (pre-selection)."""
    return {
        "sub_format_sport": row["sub_format_sport"],
        "display_label": row["display_label"],
        "is_default": bool(row["is_default"]),
    }


def sub_format_options(db, parent_sport: str | None) -> list[dict]:
    """Return the sub-format option list for a parent sport — one
    `{sub_format_sport, display_label, is_default}` dict per variant in the
    curated seed order (migration 0033 `id`), or `[]` when the parent has no
    rows (a single-format sport → no Sub-format select shown).

    Backs the server-side initial render of the race-event form's Sub-format
    `<select>` (slice B2), keyed on the currently-chosen parent. Reads the
    current canonical mapping (`superseded_at IS NULL`), same as
    `default_sub_format`.
    """
    if not parent_sport:
        return []
    cur = db.execute(
        """
        SELECT sub_format_sport, display_label, is_default
          FROM layer0.sport_sub_format_map
         WHERE parent_sport = ?
           AND superseded_at IS NULL
         ORDER BY id
        """,
        (parent_sport,),
    )
    return [_option_dict(r) for r in cur.fetchall()]


def parent_options_map(db) -> dict[str, list[dict]]:
    """Return the full `parent_sport -> [{sub_format_sport, display_label,
    is_default}, ...]` map across all sub-format parents, each list in seed
    (`id`) order.

    Serialized to a JSON blob in the race-event form so the Sub-format select
    repopulates client-side when the athlete changes the parent — the whole map
    is ~17 rows, so embedding it beats a per-change round-trip. Reads the
    current canonical mapping (`superseded_at IS NULL`).
    """
    cur = db.execute(
        """
        SELECT parent_sport, sub_format_sport, display_label, is_default
          FROM layer0.sport_sub_format_map
         WHERE superseded_at IS NULL
         ORDER BY parent_sport, id
        """
    )
    out: dict[str, list[dict]] = {}
    for r in cur.fetchall():
        out.setdefault(r["parent_sport"], []).append(_option_dict(r))
    return out
