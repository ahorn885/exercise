"""Bridge layer0-renamed exercise names back to their v1 `exercise_inventory`
display row via the EX-id crosswalk (#814).

Since #430 Slice C the prescription keys off `current_rx.layer0_exercise_id`, but
the denormalized *display* fields (discipline / type / suggested_volume /
video_reference / where_available / recovery_cost) still live in
`exercise_inventory`, keyed on the **v1 short names** ('Back Squat', 'Plank').
Plan-gen emits the **layer0 canonical names** ('Back Squat (Barbell)',
'Plank (Front)'), so a direct `ei.exercise = cr.exercise` lookup misses for
every layer0-renamed lift — its display fields come back NULL and the lift can
double-list on `/rx` (once prescribed under the layer0 name, once in the
"catalog" under the v1 name).

The bridge: an `exercise_inventory` row's v1 name maps to an EX-id through
`STRENGTH_NAME_TO_EX_ID` (the same crosswalk #698 ratified as
prescribability-sound), and the layer0-named `current_rx` row carries that
*same* EX-id (plan-gen sources it from layer0, whose canonical id for
'Back Squat (Barbell)' is the EX-id the v1 'Back Squat' was authored against).
So a layer0-named row finds its display row by EX-id even when the name misses.

Read-only and **display-only** — NOT a prescribability path (progression keys
off the EX-id directly and is unaffected). Renaming `exercise_inventory` to the
layer0 names is the wrong fix: the v1 names are load-bearing keys for the alias
crosswalk that bridges the two catalogs (#814). This bridges them instead.
"""

from __future__ import annotations

from provider_value_map_seed import STRENGTH_NAME_TO_EX_ID


def inventory_display_by_exid(rows):
    """Index `exercise_inventory` rows by the layer0 EX-id their v1 name maps to.

    `rows` is an iterable of `exercise_inventory` rows (mappings with an
    `'exercise'` key). Returns `{ex_id: row}` for every row whose v1 name resolves
    through `STRENGTH_NAME_TO_EX_ID`; rows with no crosswalk entry (a v1 name
    never renamed in layer0, or with no EX-id) are skipped.

    Deterministic: rows are consumed in the order given and the first name to
    claim an EX-id wins (a couple of EX-ids have >1 v1 alias — e.g. EX001 from
    both 'Back Squat' and 'Squat'). Callers pass an `ORDER BY exercise` fetch so
    the winner is stable.
    """
    by_exid: dict[str, object] = {}
    for row in rows:
        ex_id = STRENGTH_NAME_TO_EX_ID.get(row['exercise'])
        if ex_id:
            by_exid.setdefault(ex_id, row)
    return by_exid


def v1_names_for_exid(ex_id):
    """Candidate v1 `exercise_inventory` names for an EX-id (inverse crosswalk).

    Sorted for determinism. Empty when the EX-id has no v1 alias (e.g. a layer0
    exercise minted with no v1 catalog ancestor) — the caller then has no display
    row to bridge to.
    """
    if not ex_id:
        return []
    return sorted(name for name, x in STRENGTH_NAME_TO_EX_ID.items() if x == ex_id)
