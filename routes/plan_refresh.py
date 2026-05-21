"""D-64 plan-refresh caller-side route (Phase 5.2 caller-side).

Composes `orchestrate_plan_refresh` end-to-end:
1. GET `/plans/v2/refresh` renders the tier-picker form. If the athlete
   has no prior `plan_versions` row, renders an empty-state CTA pointing
   at `/plans/v2/new` instead — the T1/T2/T3 buttons are hidden until a
   plan exists, since plan-refresh requires a `plan_version_id_parent`.
2. POST `/plans/v2/refresh` allocates a new `plan_versions` row,
   resolves the prior-window via `load_prior_plan_session_window`, runs
   the NL parser (catching `NLParserError` → degraded
   `_default_parsed_intent()` per D-64 §5.4), invokes
   `orchestrate_plan_refresh`, persists the returned sessions, writes
   one `plan_refresh_log` row, and commits atomically per D-64 §6.2.
3. GET `/plans/v2/refresh/<plan_version_id>` renders the post-refresh
   diff view: scope dates + per-session list grouped by date with
   "updated" / "unchanged" / "new" badges computed by comparing each
   session's `payload_json` against the parent version's session in the
   same `(date, session_index_in_day)` slot. Honors D-64 §9 in v1.

Atomicity per D-64 §6.2: commit fires only after parser + orchestrator +
persistence + `plan_refresh_log` INSERT all succeed. On parser error the
route degrades to `_default_parsed_intent()` and continues — a parser
failure does NOT abort the refresh. On orchestrator/`Layer4*Error`,
nothing commits + the auto-rollback keeps the half-allocated row off the
table; a failure-row plan_refresh_log INSERT is written in a fresh
sub-transaction so the failure telemetry still lands.

Frequency caps per D-64 §8 deferred — caps are anti-cohort guard and
N=1 athlete doesn't warrant the modal-confirm UX yet. Tracked as a
follow-on per the runtime session scope.
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any, Literal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import nl_parser
from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_plan_refresh,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.plan_refresh import _default_parsed_intent
from nl_parser import IntentParserInput, NLParserError
from plan_sessions_repo import (
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    load_prior_plan_session_window,
    persist_layer4_sessions,
)
from routes.auth import current_user_id


bp = Blueprint("plan_refresh", __name__, url_prefix="/plans/v2/refresh")


VALID_TIERS = ("T1", "T2", "T3")

_TIER_HORIZON_DAYS: dict[str, int] = {"T1": 2, "T2": 7, "T3": 28}
_TIER_CREATED_VIA: dict[str, str] = {
    "T1": "plan_refresh_t1",
    "T2": "plan_refresh_t2",
    "T3": "plan_refresh_t3",
}
_TIER_DEFAULT_LAYERS_RUN: dict[str, tuple[str, ...]] = {
    "T1": ("3A", "3B", "Layer4"),
    "T2": ("3A", "3B", "Layer4"),
    "T3": ("2A", "2B", "2C", "2D", "2E", "3A", "3B", "Layer4"),
}

_NL_TEXT_SOFT_CAP_CHARS = 500


# ─── Helpers ────────────────────────────────────────────────────────────────


def _build_layer4_cache() -> Layer4Cache:
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


def _latest_plan_version(db, user_id: int) -> dict | None:
    """Return the athlete's most-recently-created plan_versions row, or
    None when the athlete has never created a plan. Scoped to user_id."""
    row = db.execute(
        "SELECT id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern "
        "FROM plan_versions WHERE user_id = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "created_at": row["created_at"],
        "created_via": row["created_via"],
        "scope_start_date": row["scope_start_date"],
        "scope_end_date": row["scope_end_date"],
        "pattern": row["pattern"],
    }


def _load_plan_version(db, user_id: int, plan_version_id: int) -> dict | None:
    """Fetch a plan_versions row scoped to user_id."""
    row = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern "
        "FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "created_at": row["created_at"],
        "created_via": row["created_via"],
        "scope_start_date": row["scope_start_date"],
        "scope_end_date": row["scope_end_date"],
        "pattern": row["pattern"],
    }


def _athlete_locale_slugs(db, user_id: int) -> tuple[str, ...]:
    rows = db.execute(
        "SELECT locale FROM locale_profiles WHERE user_id = ? ORDER BY locale",
        (user_id,),
    ).fetchall()
    return tuple(r["locale"] for r in rows if r["locale"])


def _athlete_active_injury_summary(db, user_id: int) -> tuple[str, ...]:
    """Render active injuries as human-readable strings for the NL parser
    user prompt: '<body_part> — <description or status>'. Filters on
    status = 'Active' per `injury_log.status` convention."""
    rows = db.execute(
        "SELECT body_part, description, status FROM injury_log "
        "WHERE user_id = ? AND status = 'Active' "
        "ORDER BY id",
        (user_id,),
    ).fetchall()
    summaries: list[str] = []
    for r in rows:
        body_part = (r["body_part"] or "").strip()
        if not body_part:
            continue
        descr = (r["description"] or "").strip()
        if descr:
            summaries.append(f"{body_part} — {descr}")
        else:
            summaries.append(body_part)
    return tuple(summaries)


def _parse_tier(form) -> tuple[str | None, str | None]:
    """Tier may arrive as `tier=T2` or as one of three named submit
    buttons (`submit_t1`/`submit_t2`/`submit_t3`)."""
    raw = (form.get("tier") or "").strip().upper()
    if raw in VALID_TIERS:
        return raw, None
    for tier in VALID_TIERS:
        if form.get(f"submit_{tier.lower()}") is not None:
            return tier, None
    return None, "Pick a tier (T1 / T2 / T3)."


def _resolve_scope_dates(tier: str, today: date) -> tuple[date, date]:
    """Per D-64 §3: T1 = today + tomorrow; T2 = today + 6; T3 = today + 27."""
    horizon = _TIER_HORIZON_DAYS[tier]
    return today, today + timedelta(days=horizon - 1)


_ORCH_ERROR_MESSAGES = {
    "etl_version_set_undiscoverable": "Platform data is unavailable. Try again shortly.",
    "primary_locale_missing": "Set up your home locale before refreshing your plan.",
    "framework_sport_missing": "Set your primary sport in your profile before refreshing your plan.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Plan refresh failed ({err.code}). Try again or contact support.",
    )


def _run_parser(
    db,
    user_id: int,
    *,
    nl_text: str,
    tier: str,
) -> tuple[Any, bool]:
    """Invoke the parser; on `NLParserError`, substitute the degraded
    default per D-64 §5.4. Returns `(parsed_intent, used_degraded)`."""
    parser_input = IntentParserInput(
        nl_text=nl_text,
        tier=tier,
        athlete_locales=_athlete_locale_slugs(db, user_id),
        athlete_active_injuries=_athlete_active_injury_summary(db, user_id),
    )
    try:
        return nl_parser.parse_intent(parser_input, user_id=user_id), False
    except NLParserError:
        return _default_parsed_intent(), True


def _write_refresh_log(
    db,
    *,
    user_id: int,
    tier: str,
    nl_text: str,
    parsed_intent_json: str | None,
    layers_run: tuple[str, ...],
    scope_start_date: date,
    scope_end_date: date,
    plan_version_id_before: int | None,
    plan_version_id_after: int | None,
    duration_ms: int | None,
    sessions_changed: int | None,
    success: bool,
    failure_reason: str | None,
) -> None:
    """INSERT one plan_refresh_log row. Caller owns the transaction."""
    db.execute(
        """INSERT INTO plan_refresh_log
               (user_id, tier, nl_text, parsed_intent, layers_run,
                scope_start_date, scope_end_date, plan_version_id_before,
                plan_version_id_after, duration_ms, sessions_changed,
                success, failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            tier,
            nl_text or None,
            parsed_intent_json,
            list(layers_run),
            scope_start_date,
            scope_end_date,
            plan_version_id_before,
            plan_version_id_after,
            duration_ms,
            sessions_changed,
            success,
            failure_reason,
        ),
    )


_DIFF_EXCLUDE_FIELDS = {"plan_version_id", "session_id"}
"""Fields excluded from the structural diff because the orchestrator
rebinds them on every refresh — they're identity, not content. A
refreshed session that re-emits the same training content will compare
equal to its parent slot."""


def _diff_signature(session) -> str:
    """Structural-content signature for diffing. Excludes the rebound
    identity fields per `_DIFF_EXCLUDE_FIELDS`."""
    import json

    payload = session.model_dump(mode="json", exclude=_DIFF_EXCLUDE_FIELDS)
    return json.dumps(payload, sort_keys=True)


def _diff_sessions_against_parent(
    new_sessions: list,
    parent_sessions: list,
) -> tuple[dict[tuple, str], int]:
    """Per-slot diff resolver for D-64 §9 diff visibility. Returns a
    `(date, session_index_in_day) -> 'updated' | 'unchanged' | 'new'`
    map + the count of slots that changed (updated + new).

    Compare keys: structural signature excluding `plan_version_id` +
    `session_id` (rebound on every refresh). Any other payload-field
    difference (intensity, blocks, notes, etc.) flips the slot to
    'updated'. Slots present in `new_sessions` but absent from
    `parent_sessions` are 'new' (the refresh extended the window).
    """
    parent_by_slot = {
        (s.date, s.session_index_in_day): _diff_signature(s)
        for s in parent_sessions
    }
    badges: dict[tuple, str] = {}
    changed = 0
    for s in new_sessions:
        slot = (s.date, s.session_index_in_day)
        parent_sig = parent_by_slot.get(slot)
        new_sig = _diff_signature(s)
        if parent_sig is None:
            badges[slot] = "new"
            changed += 1
        elif parent_sig != new_sig:
            badges[slot] = "updated"
            changed += 1
        else:
            badges[slot] = "unchanged"
    return badges, changed


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route("", methods=["GET", "POST"])
def refresh():
    """GET: render tier-picker form (empty state when no prior plan).
    POST: parse tier + nl_text → allocate plan_versions row → run parser
    (degraded fallback on error) → orchestrate → persist → log → commit."""
    db = get_db()
    uid = current_user_id()

    parent_plan = _latest_plan_version(db, uid)

    if request.method == "GET":
        return render_template(
            "plans/v2/refresh.html",
            parent_plan=parent_plan,
            nl_text_cap=_NL_TEXT_SOFT_CAP_CHARS,
        )

    if parent_plan is None:
        flash(
            "Create a plan before refreshing — refresh requires a parent plan version.",
            "danger",
        )
        return redirect(url_for("plan_create.new_plan"))

    tier, err = _parse_tier(request.form)
    if err is not None or tier is None:
        flash(err or "Invalid input.", "danger")
        return redirect(url_for("plan_refresh.refresh"))

    nl_text = (request.form.get("nl_context") or "").strip()
    today = date.today()
    scope_start_date, scope_end_date = _resolve_scope_dates(tier, today)

    parsed_intent, used_degraded = _run_parser(
        db, uid, nl_text=nl_text, tier=tier
    )

    parent_id: int = parent_plan["id"]
    layers_run = _TIER_DEFAULT_LAYERS_RUN[tier]

    new_plan_version_id = allocate_plan_version_row(
        db,
        uid,
        created_via=_TIER_CREATED_VIA[tier],
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
        pattern="B",
        notes=None,
    )

    started = time.monotonic()
    try:
        prior_window = load_prior_plan_session_window(
            db, uid, today=today, tier=tier
        )
        result = orchestrate_plan_refresh(
            db,
            uid,
            tier=tier,  # type: ignore[arg-type]
            refresh_scope_start=scope_start_date,
            refresh_scope_end=scope_end_date,
            plan_version_id=new_plan_version_id,
            plan_version_id_parent=parent_id,
            prior_plan_session_window=prior_window,
            cache=_build_layer4_cache(),
            parsed_intent=parsed_intent,
            today=today,
        )
    except OrchestrationError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        db.rollback()
        _write_refresh_log(
            db,
            user_id=uid,
            tier=tier,
            nl_text=nl_text,
            parsed_intent_json=parsed_intent.model_dump_json(),
            layers_run=layers_run,
            scope_start_date=scope_start_date,
            scope_end_date=scope_end_date,
            plan_version_id_before=parent_id,
            plan_version_id_after=None,
            duration_ms=duration_ms,
            sessions_changed=None,
            success=False,
            failure_reason=f"orchestration:{exc.code}",
        )
        db.commit()
        flash(_orchestration_error_message(exc), "danger")
        return redirect(url_for("plan_refresh.refresh"))
    except (Layer4InputError, Layer4OutputError) as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        db.rollback()
        _write_refresh_log(
            db,
            user_id=uid,
            tier=tier,
            nl_text=nl_text,
            parsed_intent_json=parsed_intent.model_dump_json(),
            layers_run=layers_run,
            scope_start_date=scope_start_date,
            scope_end_date=scope_end_date,
            plan_version_id_before=parent_id,
            plan_version_id_after=None,
            duration_ms=duration_ms,
            sessions_changed=None,
            success=False,
            failure_reason=f"layer4:{exc.code}",
        )
        db.commit()
        flash(
            f"Plan refresh failed ({exc.code}). Adjust your inputs and try again.",
            "danger",
        )
        return redirect(url_for("plan_refresh.refresh"))

    duration_ms = int((time.monotonic() - started) * 1000)
    persist_layer4_sessions(db, result)

    parent_sessions = load_plan_sessions_by_version(db, parent_id)
    _, sessions_changed = _diff_sessions_against_parent(
        result.sessions, parent_sessions
    )

    _write_refresh_log(
        db,
        user_id=uid,
        tier=tier,
        nl_text=nl_text,
        parsed_intent_json=parsed_intent.model_dump_json(),
        layers_run=layers_run,
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
        plan_version_id_before=parent_id,
        plan_version_id_after=new_plan_version_id,
        duration_ms=duration_ms,
        sessions_changed=sessions_changed,
        success=True,
        failure_reason="parser_degraded" if used_degraded else None,
    )
    db.commit()

    if used_degraded:
        flash(
            "NL parser unavailable — refresh ran on the default cascade only.",
            "warning",
        )
    return redirect(
        url_for(
            "plan_refresh.view_refresh", plan_version_id=new_plan_version_id
        )
    )


@bp.route("/<int:plan_version_id>", methods=["GET"])
def view_refresh(plan_version_id: int):
    """Render the post-refresh diff view: scope dates + sessions grouped
    by date with 'updated' / 'unchanged' / 'new' badges. 404 + cross-user-
    defense via the user_id filter on `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    new_sessions = load_plan_sessions_by_version(db, plan_version_id)

    parent_id = _latest_parent_for_refresh(db, uid, plan_version_id)
    parent_sessions = (
        load_plan_sessions_by_version(db, parent_id) if parent_id is not None else []
    )

    badges, sessions_changed = _diff_sessions_against_parent(
        new_sessions, parent_sessions
    )

    sessions_by_date: dict = {}
    for s in new_sessions:
        sessions_by_date.setdefault(s.date, []).append(
            {
                "session": s,
                "badge": badges.get((s.date, s.session_index_in_day), "unchanged"),
            }
        )

    return render_template(
        "plans/v2/refresh_view.html",
        plan_version=plan_version,
        sessions_by_date=sorted(sessions_by_date.items()),
        session_count=len(new_sessions),
        sessions_changed=sessions_changed,
        parent_plan_version_id=parent_id,
    )


def _latest_parent_for_refresh(
    db, user_id: int, plan_version_id: int
) -> int | None:
    """Resolve the parent plan_version_id from the most recent
    `plan_refresh_log` row pointing AT this plan_version_id. Falls back
    to the immediately-prior plan_versions row for this user when the
    log row is absent (defensive: pre-telemetry refreshes or test
    fixtures that bypass the log INSERT)."""
    row = db.execute(
        "SELECT plan_version_id_before FROM plan_refresh_log "
        "WHERE user_id = ? AND plan_version_id_after = ? "
        "ORDER BY id DESC LIMIT 1",
        (user_id, plan_version_id),
    ).fetchone()
    if row is not None and row["plan_version_id_before"] is not None:
        return int(row["plan_version_id_before"])

    fallback = db.execute(
        "SELECT id FROM plan_versions "
        "WHERE user_id = ? AND id < ? "
        "ORDER BY id DESC LIMIT 1",
        (user_id, plan_version_id),
    ).fetchone()
    if fallback is None:
        return None
    return int(fallback["id"])
