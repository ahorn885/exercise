"""Plan-create caller-side route (Phase 5.2 caller-side).

Composes `orchestrate_plan_create` end-to-end:
1. GET `/plans/v2/new` renders the create form (plan_start_date + a
   read-only summary of the athlete's existing target race, if any).
2. POST `/plans/v2/new` allocates a `plan_versions` row via
   `allocate_plan_version_row(created_via='plan_create', pattern='A')`,
   invokes `orchestrate_plan_create(...)`, persists the returned
   `Layer4Payload.sessions` via `persist_layer4_sessions`, commits the
   transaction atomically per D-64 §6.2, redirects to the plan view.
3. GET `/plans/v2/<plan_version_id>` renders the plan: scope dates +
   pattern + per-session list grouped by date.

Caller owns transaction per substrate D-64 §6.2 — `commit()` fires only
after both allocate + orchestrate + persist succeed. On any raised
exception in the chain no commit fires, the connection's auto-rollback
on close keeps the half-allocated `plan_versions` row off the table.

`notes=None` for v1; phase-synthesis-notes population from
`payload.phase_structure.phases[*].phase_synthesis_notes` requires an
`update_plan_version_notes` repo helper that doesn't exist yet —
deferred.

The form does NOT include a target-race picker — the orchestrator reads
the athlete's `is_target_event=TRUE` race from `race_events` via
`load_target_race_event_payload`. Athletes manage that on
`/profile/race-events`. Open-ended plans (no target race) are first-
class per slice 3 D4 — `race_event_payload=None` flows cleanly.
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_plan_create,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from plan_sessions_repo import (
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    persist_layer4_sessions,
)
from race_events_repo import load_target_race_event_payload
from routes.auth import current_user_id


bp = Blueprint('plan_create', __name__, url_prefix='/plans/v2')


# ─── Helpers ────────────────────────────────────────────────────────────────


def _parse_plan_start_date(form) -> tuple[date | None, str | None]:
    raw = (form.get('plan_start_date') or '').strip()
    if not raw:
        return None, "Plan start date is required."
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, "Plan start date must be in YYYY-MM-DD format."


def _load_plan_version(db, user_id: int, plan_version_id: int) -> dict | None:
    """Fetch a plan_versions row scoped to user_id. Returns dict or None."""
    row = db.execute(
        "SELECT id, user_id, created_at, created_via, scope_start_date, "
        "scope_end_date, pattern "
        "FROM plan_versions WHERE id = ? AND user_id = ?",
        (plan_version_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return {
        'id': int(row['id']),
        'user_id': int(row['user_id']),
        'created_at': row['created_at'],
        'created_via': row['created_via'],
        'scope_start_date': row['scope_start_date'],
        'scope_end_date': row['scope_end_date'],
        'pattern': row['pattern'],
    }


def _build_layer4_cache() -> Layer4Cache:
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


_ORCH_ERROR_MESSAGES = {
    'etl_version_set_undiscoverable': "Platform data is unavailable. Try again shortly.",
    'primary_locale_missing': "Set up your home locale before creating a plan.",
    'framework_sport_missing': "Set your primary sport in your profile before creating a plan.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Plan creation failed ({err.code}). Try again or contact support.",
    )


def _resolve_plan_scope_end_date(start_date: date, race_event_payload) -> date:
    """Pick a `scope_end_date` for the new plan_versions row.

    The orchestrator does not return scope bounds; for v1 we pick:
    - Race event present + event_date >= start_date → event_date.
    - Otherwise → start_date + 168 days (24-week default no-event
      ceiling per Layer 3B §6.6).
    """
    if race_event_payload is not None and getattr(race_event_payload, 'event_date', None):
        event_date = race_event_payload.event_date
        if event_date >= start_date:
            return event_date
    return start_date + timedelta(days=168)


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route('/new', methods=['GET', 'POST'])
def new_plan():
    """Render the create form on GET. On POST: parse + allocate +
    orchestrate + persist + commit atomically per D-64 §6.2."""
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        plan_start_date, err = _parse_plan_start_date(request.form)
        if err is not None or plan_start_date is None:
            flash(err or "Invalid input.", 'danger')
            return redirect(url_for('plan_create.new_plan'))

        if plan_start_date < date.today():
            flash("Plan start date must be today or in the future.", 'danger')
            return redirect(url_for('plan_create.new_plan'))

        race_event = load_target_race_event_payload(db, uid)
        scope_end_date = _resolve_plan_scope_end_date(plan_start_date, race_event)

        plan_version_id = allocate_plan_version_row(
            db, uid,
            created_via='plan_create',
            scope_start_date=plan_start_date,
            scope_end_date=scope_end_date,
            pattern='A',
            notes=None,
        )

        try:
            result = orchestrate_plan_create(
                db, uid,
                plan_start_date=plan_start_date,
                plan_version_id=plan_version_id,
                cache=_build_layer4_cache(),
            )
        except OrchestrationError as exc:
            flash(_orchestration_error_message(exc), 'danger')
            return redirect(url_for('plan_create.new_plan'))
        except (Layer4InputError, Layer4OutputError) as exc:
            flash(
                f"Plan synthesis failed ({exc.code}). Adjust your inputs and try again.",
                'danger',
            )
            return redirect(url_for('plan_create.new_plan'))

        persist_layer4_sessions(db, result)
        db.commit()
        return redirect(
            url_for('plan_create.view_plan', plan_version_id=plan_version_id)
        )

    race_event = load_target_race_event_payload(db, uid)
    return render_template(
        'plan_create/new_form.html',
        race_event=race_event,
        today_iso=date.today().isoformat(),
    )


@bp.route('/<int:plan_version_id>', methods=['GET'])
def view_plan(plan_version_id: int):
    """Render the plan: scope dates + pattern + per-session list grouped
    by date. 404 + cross-user-defense via the user_id filter in
    `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    sessions = load_plan_sessions_by_version(db, plan_version_id)
    sessions_by_date: dict = {}
    for session in sessions:
        sessions_by_date.setdefault(session.date, []).append(session)

    return render_template(
        'plan_create/view.html',
        plan_version=plan_version,
        sessions_by_date=sorted(sessions_by_date.items()),
        session_count=len(sessions),
    )
