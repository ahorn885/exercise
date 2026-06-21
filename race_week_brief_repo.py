"""Data-access helpers for the `race_week_briefs` artifact (#732 slice 2).

Pure read/write functions against the `race_week_briefs` table (one row per
`plan_version`, holding the structured `layer4.payload.RaceWeekBrief` and the
optional multi-day `RacePlan` as JSONB). No HTTP / no Flask — the race-week
brief trigger route (#732 slice 3) and the plan-view display surface consume
these helpers.

The Taper-session OVERRIDES from the same `Layer4Payload` are NOT stored here:
they are mutated back into `plan_sessions` in place via
`plan_sessions_repo.persist_layer4_sessions(..., on_conflict_update=True)` under
the athlete's active plan version (the #732 slice 2 ratified "in-place under the
active version" model). `persist_race_week_brief_result` ties the two writes
together so a caller persists a whole brief result in one call.

Mirrors the `plan_nutrition_repo` conventions: `db.execute(sql, params)` with
`?` placeholders, `model_dump_json()` into JSONB, `_decode_payload` on read,
and the caller owns the transaction boundary (these helpers do NOT commit).

Schema reference: `init_db.py` `race_week_briefs` migration. Typed contract:
`layer4/payload.py` — `RaceWeekBrief`, `RacePlan`, `Layer4Payload`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from plan_sessions_repo import persist_layer4_sessions

if TYPE_CHECKING:  # avoid pulling layer4 at import time
    from layer4.payload import Layer4Payload, RacePlan, RaceWeekBrief


def persist_race_week_brief(
    db: Any,
    user_id: int,
    plan_version_id: int,
    brief: RaceWeekBrief,
    race_plan: RacePlan | None = None,
) -> None:
    """Upsert the structured race-week brief for `plan_version_id`.

    Idempotent on `plan_version_id` (UNIQUE) — a re-fired brief overwrites the
    existing row in place rather than accumulating duplicates, matching the
    in-place mutation model of the Taper-session overrides. `event_date` +
    `race_format` are denormalized from the brief for queryability;
    `race_plan_json` is NULL for single-day events. Caller owns the transaction
    boundary — this helper does NOT call `db.commit()`.
    """
    db.execute(
        """INSERT INTO race_week_briefs
               (plan_version_id, user_id, event_date, race_format,
                brief_json, race_plan_json, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (plan_version_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                event_date = EXCLUDED.event_date,
                race_format = EXCLUDED.race_format,
                brief_json = EXCLUDED.brief_json,
                race_plan_json = EXCLUDED.race_plan_json,
                generated_at = EXCLUDED.generated_at,
                updated_at = NOW()""",
        (
            plan_version_id,
            user_id,
            brief.event_date,
            brief.race_format,
            brief.model_dump_json(),
            race_plan.model_dump_json() if race_plan is not None else None,
            datetime.now(timezone.utc),
        ),
    )


def persist_race_week_brief_result(db: Any, payload: Layer4Payload) -> None:
    """Persist a whole race-week-brief `Layer4Payload` in one call.

    Two writes, both under `payload.plan_version_id` (the athlete's active plan
    version, resolved by `orchestrate_race_week_brief`), in the caller's
    transaction:

    1. The merged Taper window (`payload.sessions`) is upserted into
       `plan_sessions` in place — `on_conflict_update=True` REPLACES the live
       Taper rows under the active version (the per-day version pointer then
       resolves any slot that previously lived under a parent version to this
       brief's override).
    2. The structured `RaceWeekBrief` + optional `RacePlan` are upserted into
       `race_week_briefs`.

    Caller owns the transaction boundary — this helper does NOT commit. The
    `payload.race_week_brief is None` guard is defensive: the race_week_brief
    driver always emits one, but a malformed payload must not silently write
    sessions with no brief home.
    """
    persist_layer4_sessions(db, payload, on_conflict_update=True)
    if payload.race_week_brief is not None:
        persist_race_week_brief(
            db,
            payload.user_id,
            payload.plan_version_id,
            payload.race_week_brief,
            payload.race_plan,
        )


def write_race_week_brief_log(
    db: Any,
    *,
    user_id: int,
    plan_version_id: int | None,
    days_to_event: int | None,
    duration_ms: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    llm_call_count: int | None,
    success: bool,
    failure_reason: str | None,
) -> None:
    """INSERT one `race_week_brief_log` row for a generation attempt (#732
    slice 4).

    Written for BOTH outcomes: a success row carries the per-attempt cost
    telemetry from the returned `Layer4Payload`; a failure row carries
    `success=FALSE` + `failure_reason` with the telemetry columns NULL (no
    payload was produced). Caller owns the transaction boundary — this helper
    does NOT commit.
    """
    db.execute(
        """INSERT INTO race_week_brief_log
               (user_id, plan_version_id, days_to_event, duration_ms,
                input_tokens, output_tokens, llm_call_count, success,
                failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            plan_version_id,
            days_to_event,
            duration_ms,
            input_tokens,
            output_tokens,
            llm_call_count,
            success,
            failure_reason,
        ),
    )


def load_race_week_brief(
    db: Any, plan_version_id: int
) -> tuple[RaceWeekBrief, RacePlan | None] | None:
    """Load the structured brief for `plan_version_id` as
    `(RaceWeekBrief, RacePlan | None)`, or None when none exists yet.

    Returns None when no brief has been generated for the plan version (the
    common case before the athlete fires the race-week brief), so callers can
    render the plan without a brief rather than erroring.
    """
    cur = db.execute(
        """SELECT brief_json, race_plan_json
             FROM race_week_briefs
            WHERE plan_version_id = ?""",
        (plan_version_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    from layer4.payload import RacePlan, RaceWeekBrief  # local: break the cycle

    brief = RaceWeekBrief.model_validate(_decode_payload(row["brief_json"]))
    raw_plan = row["race_plan_json"]
    race_plan = (
        RacePlan.model_validate(_decode_payload(raw_plan))
        if raw_plan is not None
        else None
    )
    return brief, race_plan


def _decode_payload(raw: Any) -> dict[str, Any]:
    """Normalize a JSONB column to a Python dict.

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
