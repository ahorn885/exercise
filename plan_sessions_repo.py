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
from typing import Any, Literal, NamedTuple

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
    display_name: str | None = None,
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
                pattern, notes, display_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id""",
        (
            user_id,
            created_via,
            scope_start_date,
            scope_end_date,
            pattern,
            json.dumps(notes) if notes is not None else None,
            display_name,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "INSERT INTO plan_versions RETURNING id returned no row"
        )
    return int(row["id"])


# ─── Layer 3D HITL gate persistence (#213, Layer3D_Spec §10) ─────────────────


def save_hitl_gate(db: Any, user_id: int, plan_version_id: int, gate: Any) -> None:
    """Persist a `Layer3DGate` to `plan_versions.hitl_gate` (one JSONB blob —
    items + resolutions + gate_status + evaluated_against; §10). Stamps
    `evaluated_at` if the pure gate function left it unset (§6.1 — the caller
    owns the timestamp). Writes ONLY the column; the `generation_status`
    transition to/from `needs_review` is the caller's concern. Caller owns the
    transaction boundary (no commit here)."""
    from datetime import datetime, timezone

    if getattr(gate, "evaluated_at", None) is None:
        gate = gate.model_copy(update={"evaluated_at": datetime.now(timezone.utc)})
    db.execute(
        "UPDATE plan_versions SET hitl_gate = ? WHERE id = ? AND user_id = ?",
        (json.dumps(gate.model_dump(mode="json")), plan_version_id, user_id),
    )


def load_hitl_gate(db: Any, user_id: int, plan_version_id: int) -> Any | None:
    """Load the persisted `Layer3DGate` for a plan version, or None when the
    column is NULL (no gate evaluated yet / clean athlete). Tolerates a missing
    column (pre-migration) by returning None."""
    from layer3d.gate import Layer3DGate

    try:
        row = db.execute(
            "SELECT hitl_gate FROM plan_versions WHERE id = ? AND user_id = ?",
            (plan_version_id, user_id),
        ).fetchone()
    except Exception:  # noqa: BLE001 — pre-migration column absence is non-fatal
        return None
    if row is None:
        return None
    raw = row["hitl_gate"]
    if raw is None:
        return None
    data = _decode_json(raw)
    return Layer3DGate.model_validate(data)


# ─── Layer-4 generation observations persistence (#418) ──────────────────────


def save_generation_observations(
    db: Any, user_id: int, plan_version_id: int, observations: list[Any]
) -> None:
    """Persist a plan's Layer-4 `notable_observations` (list[Observation]) to
    `plan_versions.generation_observations` — one JSONB blob, read whole by the
    operator inspect page. Caller owns the transaction (no commit here)."""
    db.execute(
        "UPDATE plan_versions SET generation_observations = ? WHERE id = ? AND user_id = ?",
        (
            json.dumps([o.model_dump(mode="json") for o in observations]),
            plan_version_id,
            user_id,
        ),
    )


def load_generation_observations(db: Any, plan_version_id: int) -> list[dict[str, Any]]:
    """Load a plan's persisted `generation_observations` (#418) for the operator
    inspect page — NOT user-scoped (admin reads any user's plan). Empty list
    when NULL or pre-migration (mirrors `load_hitl_gate`'s tolerance for a
    missing column)."""
    try:
        row = db.execute(
            "SELECT generation_observations FROM plan_versions WHERE id = ?",
            (plan_version_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001 — pre-migration column absence is non-fatal
        return []
    if row is None:
        return []
    raw = row["generation_observations"]
    if raw is None:
        return []
    return _decode_json(raw)


def load_prior_resolutions(
    db: Any, user_id: int, plan_version_id: int
) -> dict[str, Any]:
    """Extract the athlete's prior `GateResolution`s (keyed by `item_key`) for
    `evaluate_layer3d_gate(prior_resolutions=...)`. Empty dict when there's no
    gate or no resolutions yet (§5 step 5 / §6.4).

    Carries resolutions ACROSS plan versions (#213 retry-loop fix). `item_key` is
    a deterministic `sha256(source|source_item_id|discriminator)` — the *same*
    finding keeps the *same* key on a freshly-minted plan version. Previously this
    read only the current plan version's `hitl_gate`, so every [Retry] (which
    allocates a new `plan_versions` row with an empty gate) re-pended all items the
    athlete had already acknowledged — an inescapable loop. We now inherit prior
    resolutions from the athlete's other plan versions (most-recent-first), with
    the current plan's own resolutions taking precedence. A stale acknowledge can
    never mis-apply: if the underlying finding changed, its `item_key` changes and
    the old resolution simply doesn't match; a `revised` resolution whose item
    re-surfaces is re-pended by `resolved_status` regardless."""
    merged: dict[str, Any] = {}

    # Current plan version first — highest precedence — via the existing loader.
    current = load_hitl_gate(db, user_id, plan_version_id)
    if current is not None:
        for it in current.items:
            if it.resolution is not None:
                merged[it.item_key] = it.resolution

    # Inherit from the athlete's OTHER plan versions, most-recent-first, filling
    # only keys the current version hasn't already resolved. Best-effort: a
    # backend that can't serve the cross-version query (a pre-migration column, or
    # a unit stub) simply yields the current-version resolutions.
    try:
        rows = db.execute(
            "SELECT id, hitl_gate FROM plan_versions "
            "WHERE user_id = ? AND id != ? AND hitl_gate IS NOT NULL "
            "ORDER BY id DESC",
            (user_id, plan_version_id),
        ).fetchall()
    except Exception:  # noqa: BLE001 — pre-migration column absence is non-fatal
        return merged

    from layer3d.gate import Layer3DGate

    for row in rows or []:
        raw = row["hitl_gate"]
        if raw is None:
            continue
        gate = Layer3DGate.model_validate(_decode_json(raw))
        for it in gate.items:
            if it.resolution is not None and it.item_key not in merged:
                merged[it.item_key] = it.resolution
    return merged


def persist_layer4_sessions(
    db: Any, payload: Layer4Payload, *, on_conflict_update: bool = False
) -> None:
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

    `on_conflict_update` (#732 slice 2) switches the write from a plain
    INSERT to an upsert keyed on the natural key `(plan_version_id, date,
    session_index_in_day)`. Plan-create / plan-refresh INSERT under a freshly
    allocated version (no collision possible), so they leave this False. The
    race-week brief mutates the athlete's *existing* active plan version in
    place — the merged Taper window it writes collides with the live Taper
    rows already under that version — so it sets this True to REPLACE those
    rows rather than fail on the UNIQUE.

    DEFENSIVE INVARIANT: every row is written under `payload.plan_version_id`,
    NOT the per-session `session.plan_version_id`. The two should already match
    (the orchestrator stamps sessions; the cache rebinders re-stamp on a hit),
    but a per-block cached payload that escaped rebinding once leaked an OLDER
    plan's id into a NEWER plan's sessions, colliding with the older plan's rows
    on the natural-key UNIQUE `(plan_version_id, date, session_index_in_day)` ->
    a UniqueViolation that failed the whole generation at persist. Writing under
    the payload's id (the plan actually being persisted) makes a stale
    per-session id physically unable to reach the table from ANY path; a
    mismatch is logged so an upstream stamping gap stays visible, not masked.
    """
    conflict_clause = (
        """
                ON CONFLICT (plan_version_id, date, session_index_in_day)
                DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    user_id = EXCLUDED.user_id,
                    payload_json = EXCLUDED.payload_json"""
        if on_conflict_update
        else ""
    )
    for session in payload.sessions:
        if session.plan_version_id != payload.plan_version_id:
            print(
                "persist_layer4_sessions: rebinding stale session "
                f"plan_version_id={session.plan_version_id} -> "
                f"{payload.plan_version_id} (session_id={session.session_id}, "
                f"date={session.date}); upstream cache rebind was missed"
            )
            # Re-stamp the object too, so the stored payload_json blob is
            # consistent with the natural-key columns (not just the columns).
            session = session.model_copy(
                update={"plan_version_id": payload.plan_version_id}
            )
        db.execute(
            """INSERT INTO plan_sessions
                   (plan_version_id, user_id, session_id, date,
                    session_index_in_day, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)"""
            + conflict_clause,
            (
                payload.plan_version_id,
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


def load_plan_session_payload(
    db: Any, user_id: int, plan_version_id: int, date: str, session_index_in_day: int
) -> dict[str, Any] | None:
    """Load one session's raw payload dict by its natural key, user-scoped.

    Returns the decoded `PlanSession` payload dict (the shape the #681 Wave-3b
    outbound serializers consume), or None if no such row belongs to the user.
    """
    row = db.execute(
        """SELECT payload_json
             FROM plan_sessions
            WHERE plan_version_id = ? AND date = ? AND session_index_in_day = ?
              AND user_id = ?""",
        (plan_version_id, date, session_index_in_day, user_id),
    ).fetchone()
    return _decode_payload(row["payload_json"]) if row else None


def snapshot_progress_blocks(
    db: Any,
    user_id: int,
    plan_version_id: int,
    *,
    seam_phase_idx_base: int,
) -> int:
    """#321 — snapshot this plan's accepted week-blocks from `layer4_cache`
    into the durable `plan_progress_blocks` table (idempotent upsert by
    `(plan_version_id, phase_idx)`). Returns the number of blocks snapshotted.

    Reads the same per-week-block cache rows the stall backstop counts
    (`entry_point='plan_create'`, `0 <= phase_idx < seam_phase_idx_base`,
    `created_at >= pv.created_at`, user-scoped). The cached block payload is
    `{"sessions": [...], "synthesis_metadata": {...}}` (plan_create
    `_serialize_phase_result_with_meta`); each part is copied verbatim to JSONB.

    WRITE-ONLY observability side effect — `plan_progress_blocks` is NEVER an
    input to any Layer 4 cache key (the #199/#202/#294 determinism rule). Caller
    owns the transaction boundary; this helper does NOT commit.
    """
    rows = db.execute(
        """SELECT c.phase_idx, c.phase_name, c.payload_json
             FROM layer4_cache c, plan_versions pv
            WHERE pv.id = ? AND pv.user_id = ?
              AND c.user_id = ? AND c.entry_point = 'plan_create'
              AND c.phase_idx >= 0 AND c.phase_idx < ?
              AND c.created_at >= pv.created_at""",
        (plan_version_id, user_id, user_id, seam_phase_idx_base),
    ).fetchall()
    n = 0
    for row in rows:
        payload = _decode_payload(row["payload_json"])
        sessions = payload.get("sessions", [])
        meta = payload.get("synthesis_metadata")
        db.execute(
            """INSERT INTO plan_progress_blocks
                   (plan_version_id, user_id, phase_idx, phase_name,
                    sessions_json, synthesis_metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (plan_version_id, phase_idx) DO UPDATE SET
                    phase_name = EXCLUDED.phase_name,
                    sessions_json = EXCLUDED.sessions_json,
                    synthesis_metadata_json = EXCLUDED.synthesis_metadata_json,
                    snapshot_at = NOW()""",
            (
                plan_version_id, user_id, int(row["phase_idx"]),
                row["phase_name"],
                json.dumps(sessions),
                json.dumps(meta) if meta is not None else None,
            ),
        )
        n += 1
    return n


def load_progress_blocks(db: Any, plan_version_id: int) -> list[dict[str, Any]]:
    """#321 — load the durable per-block progress snapshot for `plan_version_id`,
    ordered by `phase_idx`. Returns lightweight dicts (admin inspect view), NOT
    `PlanSession`-typed, so a partial/malformed block can still be surfaced for
    debugging rather than raising on hydration."""
    cur = db.execute(
        """SELECT phase_idx, phase_name, sessions_json,
                  synthesis_metadata_json, snapshot_at
             FROM plan_progress_blocks
            WHERE plan_version_id = ?
            ORDER BY phase_idx""",
        (plan_version_id,),
    )
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        meta_raw = row["synthesis_metadata_json"]
        out.append({
            "phase_idx": int(row["phase_idx"]),
            "phase_name": row["phase_name"],
            "sessions": _decode_json(row["sessions_json"]),
            "synthesis_metadata": _decode_json(meta_raw) if meta_raw is not None else None,
            "snapshot_at": row["snapshot_at"],
        })
    return out


def load_plan_sessions_as_blocks(
    db: Any, plan_version_id: int
) -> list[dict[str, Any]]:
    """#333 — reconstruct the per-block inspect-view shape from `plan_sessions`
    for a terminal (`ready`/`failed`) plan whose `plan_progress_blocks` snapshot
    is empty (the snapshot is the in-flight signal; a finished plan's sessions
    live in `plan_sessions`, so the #321/#323 inspect view goes blank exactly
    when you want to audit the result). Groups sessions by
    `(phase_metadata.phase_name, week_in_phase)` so the per-phase composition
    a finished plan_create plan emitted is still legible. Sessions with no
    `phase_metadata` (Pattern B refresh, single_session_synthesize, ad-hoc)
    bucket into a trailing `(no phase metadata)` block so they're not dropped.

    Returns dicts in `load_progress_blocks`'s shape so the inspect template
    renders them identically; `synthesis_metadata` and `snapshot_at` are None
    because those signals only exist in the per-pass snapshot, not in the
    persisted session payload. `phase_idx` is a synthetic ordinal — it does
    NOT correspond to the orchestrator's `phase_idx` (which is per-week-block
    inside the cache layer); the name carries the meaningful identity here.
    """
    sessions = load_plan_sessions_by_version(db, plan_version_id)
    if not sessions:
        return []
    groups: dict = {}
    no_phase: list[PlanSession] = []
    for s in sessions:
        if s.phase_metadata is None:
            no_phase.append(s)
            continue
        key = (s.phase_metadata.phase_name, s.phase_metadata.week_in_phase)
        groups.setdefault(key, []).append(s)
    blocks: list[dict[str, Any]] = []
    for (phase_name, week), session_list in groups.items():
        blocks.append({
            "phase_idx": len(blocks),
            "phase_name": f"{phase_name} · week {week}",
            "sessions": [_session_to_inspect_dict(s) for s in session_list],
            "synthesis_metadata": None,
            "snapshot_at": None,
        })
    if no_phase:
        blocks.append({
            "phase_idx": len(blocks),
            "phase_name": "(no phase metadata)",
            "sessions": [_session_to_inspect_dict(s) for s in no_phase],
            "synthesis_metadata": None,
            "snapshot_at": None,
        })
    return blocks


def _session_to_inspect_dict(s: PlanSession) -> dict[str, Any]:
    """Shape a `PlanSession` to match the per-row fields the admin inspect
    template reads off `plan_progress_blocks.sessions_json` entries (date /
    discipline_name / kind / duration_min / intensity_summary /
    coaching_intent)."""
    return {
        "date": s.date.isoformat(),
        "discipline_name": s.discipline_name,
        "kind": s.kind,
        "duration_min": s.duration_min,
        "intensity_summary": s.intensity_summary,
        "coaching_intent": s.coaching_intent,
    }


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


def load_scheduled_sessions_for_window(
    db: Any,
    user_id: int,
    *,
    start: date,
    end: date,
) -> list[PlanSession]:
    """Load the athlete's *currently-scheduled* sessions over the inclusive
    date window `[start, end]`, resolved via the same D-64 §6.3 per-day
    version pointer used by `load_prior_plan_session_window`
    (`DISTINCT ON (date, session_index_in_day) ORDER BY plan_version_id
    DESC` — the latest plan version wins for any given (date, slot), so a
    refresh that re-plans today onward overrides the parent for those dates).

    Unlike the prior-window read, this is restricted to **active** plan
    versions only — `generation_status = 'ready'`, not archived, not
    completed — so a stale/shelved/in-flight version can never surface a
    session as "scheduled". (We deliberately do NOT filter `superseded_at`:
    a tier-1/2 refresh supersedes the parent but only re-plans a short
    window, so the parent still legitimately owns its non-refreshed tail —
    the per-day `plan_version_id DESC` pointer is what resolves an overlap.)
    This is the read the dashboard uses for the Today / Tomorrow cards (the
    prior-window read is strictly pre-today and applies no status filter).

    Returns the de-duplicated `list[PlanSession]` ordered by
    (date ascending, session_index_in_day ascending); `[]` when the athlete
    has no active sessions in the window.
    """
    cur = db.execute(
        """SELECT DISTINCT ON (s.date, s.session_index_in_day)
                  s.payload_json
             FROM plan_sessions s
             JOIN plan_versions pv ON pv.id = s.plan_version_id
            WHERE s.user_id = ?
              AND s.date BETWEEN ? AND ?
              AND pv.generation_status = 'ready'
              AND pv.archived_at IS NULL
              AND pv.completed_at IS NULL
            ORDER BY s.date, s.session_index_in_day, s.plan_version_id DESC""",
        (user_id, start, end),
    )
    return [
        PlanSession.model_validate(_decode_payload(row["payload_json"]))
        for row in cur.fetchall()
    ]


def load_active_plan_version_id(db: Any, user_id: int) -> int | None:
    """Return the athlete's currently-active plan version id, or None.

    Active := `generation_status = 'ready'`, not archived, not completed —
    the same predicate `load_scheduled_sessions_for_window` filters on for
    "what's currently scheduled". The most-recently-created qualifying row
    wins: a T1/T2/T3 refresh supersedes its parent for the dates it
    re-plans but both stay `ready`, and the latest version is the one the
    race-week brief attaches its Taper-session overrides to.

    Returns None when the athlete has no active plan version (never created
    a plan, or only has in-flight / archived / completed versions). The
    race-week-brief orchestrator treats that as `no_active_plan` — the brief
    has nothing to attach its overrides to.
    """
    row = db.execute(
        "SELECT id FROM plan_versions "
        "WHERE user_id = ? AND generation_status = 'ready' "
        "AND archived_at IS NULL AND completed_at IS NULL "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def load_active_plan_version_for_date(
    db: Any, user_id: int, on_date: date
) -> dict[str, Any] | None:
    """Return the active plan version whose scope *covers* `on_date` (its `id`
    plus scope dates), or None.

    "Active" mirrors `load_scheduled_sessions_for_window` /
    `load_active_plan_version_id`: `generation_status = 'ready'`, not archived,
    not completed. The added scope-cover predicate (`scope_start_date <=
    on_date <= scope_end_date`) lets the caller distinguish "this date sits
    inside an active plan" from "no plan at all". The most-recently-created
    qualifying version wins on overlap (a T1/T2/T3 refresh and its parent are
    both `ready`), matching the per-day pointer's `plan_version_id DESC`.

    The dashboard uses this to render a scheduled REST day on the Today /
    Tomorrow cards: the v2 generator encodes ordinary rest days as the ABSENCE
    of a session (per_phase `=== Schedule ===` — "Disabled days are rest
    days"), so a date that carries no session but still falls inside an active
    plan's scope is a rest day, not the "no plan" empty state (#888). Returns
    None when no active plan covers the date (the genuine no-session case).
    """
    row = db.execute(
        "SELECT id, scope_start_date, scope_end_date FROM plan_versions "
        "WHERE user_id = ? AND generation_status = 'ready' "
        "AND archived_at IS NULL AND completed_at IS NULL "
        "AND scope_start_date <= ? AND scope_end_date >= ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (user_id, on_date, on_date),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "scope_start_date": row["scope_start_date"],
        "scope_end_date": row["scope_end_date"],
    }


def load_current_plan_start(
    db: Any, user_id: int, on_or_before: date
) -> date | None:
    """Return the start date of the athlete's currently-running plan — the
    `scope_start_date` of the most recent `created_via = 'plan_create'`
    `plan_versions` row that began on or before `on_or_before` — or None when
    the athlete has never created a plan.

    Why not the active version's `scope_start_date`: `plan_versions` carries no
    parent pointer, and a refresh writes a NEW version scoped to the *refresh*
    window (`created_via = 'plan_refresh_t*'`). So the active version's scope
    start is the last edit, not where periodization phase 0 began. The original
    full plan is the `plan_create` row, and its `scope_start_date` is the anchor
    `plan_management.derive_current_phase` (§5.1) needs to place today's phase
    (#1024). The `<= on_or_before` filter + `created_at DESC` picks the latest
    plan the athlete actually started, so a full re-create supersedes an older
    plan rather than both being ambiguous. No `archived_at`/`completed_at`
    filter: a `plan_create` row stays the origin even after refreshes supersede
    it for the dates they re-plan."""
    row = db.execute(
        "SELECT scope_start_date FROM plan_versions "
        "WHERE user_id = ? AND created_via = 'plan_create' "
        "AND scope_start_date <= ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (user_id, on_or_before),
    ).fetchone()
    return row["scope_start_date"] if row else None


def _coerce_day(value: Any) -> date | None:
    """Coerce a session-map key to a `date`. psycopg returns DATE as `date`
    already; tolerate ISO strings (and the render harness's fake keys) and
    return None for anything unparseable so a bad key degrades to a no-fill
    passthrough rather than raising."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def fill_rest_gaps(
    sessions_by_date: dict[Any, list[PlanSession]],
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[tuple[Any, str, list[PlanSession]]]:
    """THE rest-day-as-absence rule, in one place (#618/#888).

    Given `{date: [PlanSession, ...]}`, return an ordered list of
    `(date, day_of_week, sessions)` covering every calendar day in the range,
    where a day with no persisted session surfaces as an explicit REST day
    (empty `sessions`). The v2 generator schedules NO session on a rest day
    (per_phase `=== Schedule ===` — "Disabled days are rest days"), so every
    surface that renders "what's on day X" must fill those gaps; centralizing
    it here keeps the plan's daily view and the home Today/Tomorrow cards from
    drifting apart (the #888 regression).

    Range: `[start, end]` inclusive when given; otherwise derived from the
    first/last session date (the daily-view default). An explicit range lets a
    caller fill days even when `sessions_by_date` is empty (a fully-rest
    window). Pure — no DB, no I/O.

    Keys that can't be coerced to a `date` (render-harness fakes) and no
    explicit range → passthrough the dated days as-is, no synthetic gaps.
    """
    coerced = [(_coerce_day(d), d, ss) for d, ss in sessions_by_date.items()]
    if start is None and end is None and any(cd is None for cd, _, _ in coerced):
        ordered = sorted(coerced, key=lambda t: str(t[1]))
        return [(raw, (ss[0].day_of_week if ss else ""), ss)
                for _cd, raw, ss in ordered]
    by_date = {cd: ss for cd, _raw, ss in coerced if cd is not None}
    if start is None and end is None:
        if not by_date:
            return []
        keys = sorted(by_date)
        start, end = keys[0], keys[-1]
    elif start is None:
        start = min(by_date) if by_date else end
    elif end is None:
        end = max(by_date) if by_date else start
    days: list[tuple[Any, str, list[PlanSession]]] = []
    d = start
    while d <= end:
        days.append((d, d.strftime("%a"), by_date.get(d, [])))
        d += timedelta(days=1)
    return days


class DayPlan(NamedTuple):
    """One day of an active-schedule window (`load_active_window_with_rest`).
    `sessions` empty == an explicit REST day; `plan` carries the covering
    active plan version (id + scope) on rest days so the surface can still link
    back to the plan, and is None on session-bearing days (the session already
    carries its `plan_version_id`)."""

    date: date
    day_of_week: str
    sessions: list[PlanSession]
    plan: dict[str, Any] | None


def load_active_window_with_rest(
    db: Any, user_id: int, *, start: date, end: date
) -> list[DayPlan]:
    """Per-day active schedule over `[start, end]`, with covered-but-empty days
    surfaced as explicit REST and days no active plan covers OMITTED.

    Composes the three single-purpose reads so every "what's scheduled on these
    days" surface shares one rest-aware resolver (#888):
    - `load_scheduled_sessions_for_window` — the active per-day version pointer
      supplies each day's sessions;
    - `fill_rest_gaps` — applies the rest-day-as-absence rule across the window;
    - `load_active_plan_version_for_date` — gates each empty (gap) day on active
      scope coverage, so a gap INSIDE a plan becomes rest while a gap with no
      active plan is omitted (a genuine no-plan day, not a rest day) and carries
      the covering plan so a rest day can name/link its plan.

    The dashboard Today/Tomorrow cards consume this; any future window surface
    (e.g. a week strip) gets rest days for free.
    """
    sessions = load_scheduled_sessions_for_window(db, user_id, start=start, end=end)
    by_date: dict[date, list[PlanSession]] = {}
    for s in sessions:
        by_date.setdefault(s.date, []).append(s)
    out: list[DayPlan] = []
    for d, dow, day_sessions in fill_rest_gaps(by_date, start=start, end=end):
        if day_sessions:
            out.append(DayPlan(d, dow, day_sessions, None))
            continue
        pv = load_active_plan_version_for_date(db, user_id, d)
        if pv is not None:
            out.append(DayPlan(d, dow, [], pv))
        # else: no active plan covers d — omit (a genuine no-session day).
    return out


def _decode_json(raw: Any) -> Any:
    """Type-agnostic JSONB normalizer (dict, list, or JSON string). Unlike
    `_decode_payload`, tolerates a JSON *array* column (e.g. the
    `plan_progress_blocks.sessions_json` session list)."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


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
