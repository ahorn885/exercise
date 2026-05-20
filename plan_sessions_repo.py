"""Data-access helpers for the v2 plan-version + plan-session persistence
substrate (Phase 5.2 caller-side foundation, 2026-05-20).

Pure read/write functions against `plan_versions` + `plan_sessions`. No
HTTP / no Flask blueprint — the D-63 + D-64 + plan-create route arcs
consume these helpers to allocate the version row before invoking the
Layer 4 orchestrator entry point and to persist the returned
`Layer4Payload.sessions` after the orchestrator returns.

Schema reference: `Layer4_Spec.md` §7.11 (`plan_versions`) + §7.12
schema-level rules (`PlanSession` natural key + invariants); D-64 §6.2
(atomic-write semantics — caller owns the transaction boundary) + §6.3
(per-day version pointer resolver).

Typed contract: `layer4/payload.py` — Layer4Payload + PlanSession.

`prior_plan_session_window` lookback window: tier-tied default mapping
T1=2 days / T2=7 days / T3=28 days (matches the refresh forward-scope
shape so the prior window roughly mirrors what's about to change).
Caller can override via the `days` kwarg.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Literal

from layer4.payload import Layer4Payload, PlanSession


VALID_CREATED_VIA = (
    "plan_create",
    "plan_refresh_t1",
    "plan_refresh_t2",
    "plan_refresh_t3",
    "single_session_synthesize",
)

VALID_PATTERN = ("A", "B")

_PRIOR_WINDOW_DAYS_BY_TIER: dict[str, int] = {"T1": 2, "T2": 7, "T3": 28}


def allocate_plan_version_row(
    db: Any,
    user_id: int,
    *,
    created_via: str,
    scope_start_date: date,
    scope_end_date: date,
    pattern: str,
    notes: dict[str, Any] | None = None,
) -> int:
    """Allocate a new `plan_versions` row and return the assigned id.

    Caller invokes this BEFORE calling the Layer 4 orchestrator entry
    point so the resulting `plan_version_id` can be threaded through to
    `orchestrate_plan_create` / `orchestrate_plan_refresh` /
    `orchestrate_single_session_synthesize`. The orchestrator stamps the
    returned `Layer4Payload.plan_version_id` + every nested
    `PlanSession.plan_version_id` to this value (cache hits also rebind
    per §9.4); `persist_layer4_sessions` then writes the rows under it.

    Caller owns the transaction boundary per D-64 §6.2. This helper does
    NOT call `db.commit()`.
    """
    if created_via not in VALID_CREATED_VIA:
        raise ValueError(
            f"created_via={created_via!r} not in {VALID_CREATED_VIA}"
        )
    if pattern not in VALID_PATTERN:
        raise ValueError(f"pattern={pattern!r} not in {VALID_PATTERN}")
    if scope_end_date < scope_start_date:
        raise ValueError(
            f"scope_end_date={scope_end_date} < scope_start_date={scope_start_date}"
        )

    cur = db.execute(
        """INSERT INTO plan_versions
               (user_id, created_via, scope_start_date, scope_end_date,
                pattern, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id""",
        (
            user_id,
            created_via,
            scope_start_date,
            scope_end_date,
            pattern,
            json.dumps(notes) if notes is not None else None,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "INSERT INTO plan_versions RETURNING id returned no row"
        )
    return int(row["id"])


def persist_layer4_sessions(db: Any, payload: Layer4Payload) -> None:
    """Persist every `PlanSession` in `payload.sessions` to `plan_sessions`.

    Each row carries the full `PlanSession.model_dump(mode='json')` as
    `payload_json` plus the denormalized natural-key columns
    (`plan_version_id`, `date`, `session_index_in_day`) and `user_id` for
    fast (user_id, date) lookups.

    Caller owns the transaction boundary per D-64 §6.2 — this helper
    does NOT call `db.commit()`. On INSERT failure (e.g., natural-key
    UNIQUE collision when the orchestrator emits a duplicate slot)
    the caller's transaction can be rolled back atomically.

    `payload.sessions` may be empty (e.g., a no-op Pattern B refresh in
    edge cases); the helper is a no-op in that case.
    """
    for session in payload.sessions:
        # session.plan_version_id is stamped by the orchestrator (or the
        # cache rebinder on hit per §9.4); the natural-key UNIQUE
        # constraint will reject duplicates within a single plan_version_id.
        db.execute(
            """INSERT INTO plan_sessions
                   (plan_version_id, user_id, session_id, date,
                    session_index_in_day, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session.plan_version_id,
                payload.user_id,
                session.session_id,
                session.date,
                session.session_index_in_day,
                session.model_dump_json(),
            ),
        )


def load_plan_sessions_by_version(
    db: Any, plan_version_id: int
) -> list[PlanSession]:
    """Load all `PlanSession` rows for `plan_version_id`, ordered by
    (date, session_index_in_day).

    Used by tests + future plan-view "show me everything that landed
    under this version" queries. Does NOT apply the per-day version
    pointer resolver (use `load_prior_plan_session_window` for the
    multi-version "what's currently scheduled" query).
    """
    cur = db.execute(
        """SELECT payload_json
             FROM plan_sessions
            WHERE plan_version_id = ?
            ORDER BY date, session_index_in_day""",
        (plan_version_id,),
    )
    return [
        PlanSession.model_validate(_decode_payload(row["payload_json"]))
        for row in cur.fetchall()
    ]


def load_prior_plan_session_window(
    db: Any,
    user_id: int,
    *,
    today: date,
    tier: Literal["T1", "T2", "T3"] | None = None,
    days: int | None = None,
) -> list[PlanSession]:
    """Load the athlete's prior plan-session window via D-64 §6.3 per-day
    version pointer (`DISTINCT ON (date, session_index_in_day) ORDER BY
    plan_version_id DESC`).

    Window covers `[today - days, today - 1]` inclusive — strictly
    pre-today; the refresh/create entry points produce sessions from
    `today` onward, so the prior window doesn't overlap.

    Lookback resolution:
    - `days` non-None → use directly (caller override; e.g., a custom
      "last 6 weeks" race-week-brief window).
    - `days` None + `tier` non-None → tier-tied default per
      `_PRIOR_WINDOW_DAYS_BY_TIER` (T1=2 / T2=7 / T3=28). Matches the
      refresh forward-scope shape.
    - Both None → ValueError (caller must specify at least one).

    Returns the de-duplicated `list[PlanSession]` ordered by
    (date ascending, session_index_in_day ascending). When the athlete
    has no prior sessions (first plan_create), returns `[]` — the
    caller is responsible for deciding whether a non-empty window is
    required (Layer 4 `plan_refresh` driver enforces non-empty per its
    own `_validate_inputs`).
    """
    if days is None and tier is None:
        raise ValueError(
            "at least one of `tier` or `days` must be provided"
        )
    if days is None:
        days = _PRIOR_WINDOW_DAYS_BY_TIER[tier]  # type: ignore[index]
    if days <= 0:
        raise ValueError(f"days={days} must be positive")

    cutoff_start = today - timedelta(days=days)
    cutoff_end = today - timedelta(days=1)

    cur = db.execute(
        """SELECT DISTINCT ON (date, session_index_in_day)
                  payload_json
             FROM plan_sessions
            WHERE user_id = ?
              AND date BETWEEN ? AND ?
            ORDER BY date, session_index_in_day, plan_version_id DESC""",
        (user_id, cutoff_start, cutoff_end),
    )
    return [
        PlanSession.model_validate(_decode_payload(row["payload_json"]))
        for row in cur.fetchall()
    ]


def _decode_payload(raw: Any) -> dict[str, Any]:
    """Normalize the `payload_json` column to a Python dict.

    psycopg2 with the default JSONB adapter returns a dict directly;
    the historical SQLite shim path returns a JSON string. Both are
    tolerated for symmetry with the rest of the repo layer (see
    `race_events_repo.get_race_event` for the same dual-path pattern).
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise TypeError(
        f"payload_json must be dict or JSON string, got {type(raw).__name__}"
    )
