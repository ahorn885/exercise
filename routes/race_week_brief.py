"""#732 slice 3 — race-week-brief caller-side route.

Composes `orchestrate_race_week_brief` end-to-end, mirroring the on-demand
single-session (`routes/ad_hoc_workouts.py`) and plan-refresh
(`routes/plan_refresh.py`) caller arcs:

1. POST `/plans/v2/brief/generate` — the [Generate race-week brief] button on
   the plan view (shown only when `days_to_event <= 14`, the orchestrator's
   auto-fire gate). Invokes the orchestrator (which resolves the athlete's
   active plan version + prior Taper window internally per slice 1), persists
   the result via `persist_race_week_brief_result` (the merged Taper window
   upserted into `plan_sessions` in place + the structured brief into
   `race_week_briefs`, slice 2), commits, and redirects to the brief view.
2. GET `/plans/v2/brief/<plan_version_id>` — renders the stored brief: kit
   manifest, fueling, pacing, contingencies, mental-prep, and (multi-day only)
   the structured race plan.

Atomic per the substrate D-64 §6.2 contract: the commit fires only after the
orchestrator + persistence both succeed. On `OrchestrationError` /
`Layer3*OutputError` / `Layer4*Error` nothing commits (the connection's
auto-rollback keeps the in-place upsert out of the table) and a `flash()` +
redirect surfaces the failure to the athlete.
"""

from __future__ import annotations

import time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_race_week_brief,
)
from layer3a.builder import Layer3AOutputError
from layer3b.builder import Layer3BOutputError
from layer4.errors import Layer4InputError, Layer4OutputError
from race_week_brief_repo import (
    load_race_week_brief,
    persist_race_week_brief_result,
    write_race_week_brief_log,
)
from routes.auth import current_user_id


bp = Blueprint("race_week_brief", __name__, url_prefix="/plans/v2/brief")


_ORCH_ERROR_MESSAGES = {
    "no_target_event": "Set a target race before generating a race-week brief.",
    "race_week_brief_too_early": "The race-week brief unlocks within 14 days of your event.",
    "no_active_plan": "Create a plan before generating a race-week brief.",
    "etl_version_set_undiscoverable": "Platform data is unavailable. Try again shortly.",
    "primary_locale_missing": "Set up your home locale before generating a race-week brief.",
    "framework_sport_missing": "Set your primary sport in your profile before generating a race-week brief.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Race-week brief failed ({err.code}). Try again or contact support.",
    )


def _build_layer4_cache() -> Layer4Cache:
    """Layer 4 cache wired to the per-request DB connection (mirrors the
    sibling caller routes)."""
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


def _owns_plan_version(db, user_id: int, plan_version_id: int) -> bool:
    """Cross-user defense: True when `plan_version_id` belongs to `user_id`."""
    row = db.execute(
        "SELECT 1 FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, user_id),
    ).fetchone()
    return row is not None


def _plan_view_redirect(plan_version_id: int | None):
    """Redirect back to the originating plan view when we know it, else the
    dashboard. Used for the error path off the POST."""
    if plan_version_id is not None:
        return redirect(
            url_for("plan_create.view_plan", plan_version_id=plan_version_id)
        )
    return redirect(url_for("dashboard.index"))


def _form_plan_version_id() -> int | None:
    """The plan view stamps its own plan_version_id on the generate form so the
    error path can bounce the athlete back to it. Tampering / absence collapses
    to None (→ dashboard)."""
    raw = request.form.get("plan_version_id")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _log_brief_failure(db, user_id, plan_version_id, *, failure_reason):
    """Best-effort failure telemetry (#732 slice 4). The orchestrator failure
    aborts the in-flight transaction, so roll it back, land a `success=FALSE`
    row, and commit JUST the log. Swallows its own errors so a logging fault
    never masks the athlete's flash + redirect."""
    try:
        db.rollback()
        write_race_week_brief_log(
            db,
            user_id=user_id,
            plan_version_id=plan_version_id,
            days_to_event=None,
            duration_ms=None,
            input_tokens=None,
            output_tokens=None,
            llm_call_count=None,
            success=False,
            failure_reason=failure_reason,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — telemetry must never break the route
        print(f"race_week_brief: failure-log write failed (non-fatal): {exc}")


@bp.route("/generate", methods=["POST"])
def generate_brief():
    """Invoke the orchestrator, persist the result, log the attempt, commit,
    redirect to the brief view. The orchestrator resolves the active plan
    version + prior Taper window itself (slice 1), so no inputs are needed
    beyond the user. Every attempt — success or failure — lands one
    `race_week_brief_log` row (slice 4)."""
    db = get_db()
    uid = current_user_id()
    origin_plan_version_id = _form_plan_version_id()

    started = time.monotonic()
    try:
        result = orchestrate_race_week_brief(db, uid, cache=_build_layer4_cache())
    except OrchestrationError as exc:
        _log_brief_failure(db, uid, origin_plan_version_id, failure_reason=exc.code)
        flash(_orchestration_error_message(exc), "danger")
        return _plan_view_redirect(origin_plan_version_id)
    except (
        Layer3AOutputError,
        Layer3BOutputError,
        Layer4InputError,
        Layer4OutputError,
    ) as exc:
        # 3A/3B run upstream in the same cone, so their OutputErrors surface here
        # alongside the Layer 4 errors rather than 500-ing.
        _log_brief_failure(db, uid, origin_plan_version_id, failure_reason=exc.code)
        flash(
            f"Race-week brief synthesis failed ({exc.code}). Try again shortly.",
            "danger",
        )
        return _plan_view_redirect(origin_plan_version_id)

    duration_ms = int((time.monotonic() - started) * 1000)
    persist_race_week_brief_result(db, result)
    write_race_week_brief_log(
        db,
        user_id=uid,
        plan_version_id=result.plan_version_id,
        days_to_event=(
            result.race_week_brief.days_to_event if result.race_week_brief else None
        ),
        duration_ms=duration_ms,
        input_tokens=result.input_tokens_total,
        output_tokens=result.output_tokens_total,
        llm_call_count=result.llm_call_count,
        success=True,
        failure_reason=None,
    )
    db.commit()
    return redirect(
        url_for("race_week_brief.view_brief", plan_version_id=result.plan_version_id)
    )


@bp.route("/<int:plan_version_id>", methods=["GET"])
def view_brief(plan_version_id: int):
    """Render the stored race-week brief + (multi-day) race plan. 404 on a
    missing/foreign plan version or when no brief has been generated yet."""
    db = get_db()
    uid = current_user_id()

    if not _owns_plan_version(db, uid, plan_version_id):
        abort(404)

    loaded = load_race_week_brief(db, plan_version_id)
    if loaded is None:
        abort(404)
    brief, race_plan = loaded

    return render_template(
        "plans/v2/race_week_brief.html",
        plan_version_id=plan_version_id,
        brief=brief,
        race_plan=race_plan,
    )
