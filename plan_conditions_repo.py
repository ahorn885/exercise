"""Data-access helpers for the Layer 5B `plan_conditions` artifact.

Pure read/write functions against the `plan_conditions` table (one row per
`plan_version`, holding the whole `layer5.PlanConditions` bundle as JSONB). No
HTTP / no Flask — the post-plan conditions trigger and the plan-view route
consume these helpers.

Mirrors `plan_nutrition_repo`: `db.execute(sql, params)` with `?` placeholders,
`model_dump_json()` into JSONB, `_decode_payload` on read, and the caller owns
the transaction boundary (these helpers do NOT commit).

Schema reference: `init_db.py` `plan_conditions` migration. Typed contract:
`layer5/conditions_payload.py` — `PlanConditions`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid an import cycle (layer5 -> orchestrator -> this module)
    from layer5.conditions_payload import PlanConditions


def persist_plan_conditions(
    db: Any, user_id: int, conditions: PlanConditions
) -> None:
    """Upsert the `PlanConditions` bundle for its plan version.

    Idempotent on `plan_version_id` (UNIQUE) — a regenerate overwrites the
    existing row in place rather than accumulating duplicates. The full bundle
    is stored as `payload_json`; `model` is denormalized so a future
    model-version bump can locate stale artifacts. Caller owns the transaction
    boundary — this helper does NOT call `db.commit()`.
    """
    db.execute(
        """INSERT INTO plan_conditions
               (plan_version_id, user_id, model, payload_json, generated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (plan_version_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                model = EXCLUDED.model,
                payload_json = EXCLUDED.payload_json,
                generated_at = EXCLUDED.generated_at,
                updated_at = NOW()""",
        (
            conditions.plan_version_id,
            user_id,
            conditions.model_meta.model,
            conditions.model_dump_json(),
            conditions.generated_at,
        ),
    )


def load_plan_conditions_by_version(
    db: Any, plan_version_id: int
) -> PlanConditions | None:
    """Load the `PlanConditions` bundle for `plan_version_id`, or None.

    Returns None when no artifact exists yet (e.g. the plan reached `ready` but
    the conditions stage has not run, or no session locale carried coordinates)
    so callers can render the plan without conditions rather than erroring.
    """
    cur = db.execute(
        """SELECT payload_json
             FROM plan_conditions
            WHERE plan_version_id = ?""",
        (plan_version_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    from layer5.conditions_payload import PlanConditions  # local import breaks cycle

    return PlanConditions.model_validate(_decode_payload(row["payload_json"]))


def _decode_payload(raw: Any) -> dict[str, Any]:
    """Normalize the `payload_json` column to a Python dict.

    psycopg2's JSONB adapter returns a dict directly; the historical SQLite
    shim path returns a JSON string. Both are tolerated for symmetry with
    `plan_nutrition_repo._decode_payload`.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise TypeError(
        f"payload_json must be dict or JSON string, got {type(raw).__name__}"
    )
