"""Data-access helpers for the Layer 5A `plan_nutrition` artifact.

Pure read/write functions against the `plan_nutrition` table (one row per
`plan_version`, holding the whole `layer5.PlanNutrition` bundle as JSONB). No
HTTP / no Flask — the post-plan nutrition trigger and the plan-view route
consume these helpers.

Mirrors the `plan_sessions_repo` conventions: `db.execute(sql, params)` with
`?` placeholders, `model_dump_json()` into JSONB, `_decode_payload` on read,
and the caller owns the transaction boundary (these helpers do NOT commit).

Schema reference: `init_db.py` `plan_nutrition` migration. Typed contract:
`layer5/payload.py` — `PlanNutrition`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid an import cycle (layer5 -> orchestrator -> this module)
    from layer5.payload import PlanNutrition


def persist_plan_nutrition(
    db: Any, user_id: int, nutrition: PlanNutrition
) -> None:
    """Upsert the `PlanNutrition` bundle for its plan version.

    Idempotent on `plan_version_id` (UNIQUE) — a regenerate overwrites the
    existing row in place rather than accumulating duplicates. The full bundle
    is stored as `payload_json`; `energy_model` is denormalized so a future
    model-version bump can locate stale artifacts. Caller owns the transaction
    boundary — this helper does NOT call `db.commit()`.
    """
    db.execute(
        """INSERT INTO plan_nutrition
               (plan_version_id, user_id, energy_model, payload_json, generated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (plan_version_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                energy_model = EXCLUDED.energy_model,
                payload_json = EXCLUDED.payload_json,
                generated_at = EXCLUDED.generated_at,
                updated_at = NOW()""",
        (
            nutrition.plan_version_id,
            user_id,
            nutrition.energy_model.model,
            nutrition.model_dump_json(),
            nutrition.generated_at,
        ),
    )


def load_plan_nutrition_by_version(
    db: Any, plan_version_id: int
) -> PlanNutrition | None:
    """Load the `PlanNutrition` bundle for `plan_version_id`, or None.

    Returns None when no artifact exists yet (e.g. the plan reached `ready`
    but the nutrition stage has not run, or is still pending/failed) so callers
    can render the plan without nutrition rather than erroring.
    """
    cur = db.execute(
        """SELECT payload_json
             FROM plan_nutrition
            WHERE plan_version_id = ?""",
        (plan_version_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    from layer5.payload import PlanNutrition  # local import breaks the cycle

    return PlanNutrition.model_validate(_decode_payload(row["payload_json"]))


def persist_plan_nutrition_inputs(
    db: Any,
    user_id: int,
    plan_version_id: int,
    *,
    layer2e_payload_json: dict[str, Any],
    body_weight_kg: float,
    event_dates: dict[str, str],
) -> None:
    """Upsert the Layer 5A inputs snapshot for `plan_version_id`.

    `layer2e_payload_json` is `Layer2EPayload.model_dump(mode="json")`;
    `event_dates` maps event_id -> ISO date string (matching the
    `RaceDayFueling.event_id` keys). Idempotent on `plan_version_id`. Caller
    owns the transaction boundary — this helper does NOT commit.
    """
    blob = {
        "layer2e_payload": layer2e_payload_json,
        "body_weight_kg": body_weight_kg,
        "event_dates": event_dates,
    }
    db.execute(
        """INSERT INTO plan_nutrition_inputs
               (plan_version_id, user_id, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT (plan_version_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                payload_json = EXCLUDED.payload_json,
                updated_at = NOW()""",
        (plan_version_id, user_id, json.dumps(blob)),
    )


def load_plan_nutrition_inputs(
    db: Any, plan_version_id: int
) -> dict[str, Any] | None:
    """Load the Layer 5A inputs snapshot for `plan_version_id`, or None.

    Returns the decoded blob ``{"layer2e_payload": ..., "body_weight_kg": ...,
    "event_dates": ...}``. None when no snapshot exists (e.g. a plan generated
    before this feature shipped, or an open-ended plan whose generation predates
    the stash) — callers treat that as "nutrition not available".
    """
    cur = db.execute(
        """SELECT payload_json
             FROM plan_nutrition_inputs
            WHERE plan_version_id = ?""",
        (plan_version_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return _decode_payload(row["payload_json"])


def _decode_payload(raw: Any) -> dict[str, Any]:
    """Normalize the `payload_json` column to a Python dict.

    psycopg2's JSONB adapter returns a dict directly; the historical SQLite
    shim path returns a JSON string. Both are tolerated for symmetry with
    `plan_sessions_repo._decode_payload`.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise TypeError(
        f"payload_json must be dict or JSON string, got {type(raw).__name__}"
    )
