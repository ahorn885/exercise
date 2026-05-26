"""Plan-create caller-side route (Phase 5.2 caller-side).

Generation is asynchronous + resumable so it survives the serverless
function timeout — the full Layer 3A → 3B → per-phase Layer 4 cone is many
sequential extended-thinking LLM calls (minutes of wall-clock), far past
any single request budget. The flow:

1. GET `/plans/v2/new` renders the create form (plan_start_date + a
   read-only summary of the athlete's existing target race, if any).
2. POST `/plans/v2/new` allocates a `plan_versions` row via
   `allocate_plan_version_row(created_via='plan_create', pattern='A')`,
   marks it `generation_status='generating'`, commits, and redirects to
   the progress screen. No LLM work runs in this request.
3. GET `/plans/v2/<id>/progress` renders a progress screen whose JS polls
   POST `/plans/v2/<id>/generate`.
4. POST `/plans/v2/<id>/generate` runs one `orchestrate_plan_create` pass.
   Each upstream layer + per-phase synthesis is individually cached +
   committed in `layer4_cache`, so a pass cut short by the function
   timeout resumes from the cache on the next poll. On completion the
   sessions persist atomically + the row flips to `ready`; a typed
   upstream error flips it to `failed`.
5. GET `/plans/v2/<id>` renders the plan once `ready` (scope dates +
   pattern + per-session list grouped by date); `generating` redirects to
   the progress screen, `failed` flashes the error.

Caller owns the transaction per substrate D-64 §6.2 — `generate_plan`'s
final `commit()` fires only after orchestrate + persist succeed. On any
raised exception no commit fires; the connection's auto-rollback on close
keeps partial sessions off the table (re-persist is also DELETE-guarded).

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

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_plan_create,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer3a.builder import Layer3AOutputError
from layer3b.builder import Layer3BOutputError
from plan_sessions_repo import (
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    persist_layer4_sessions,
)
from race_events_repo import load_target_race_event_payload
from routes.auth import cron_authorized, current_user_id


bp = Blueprint('plan_create', __name__, url_prefix='/plans/v2')

# Max `generating` rows the cron advances per fire. Bounds one invocation's
# wall-clock (each pass is up to the function-duration cap) so the scanner
# can't run unboundedly; remaining rows are picked up on the next fire.
_CRON_ADVANCE_BATCH = 5


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
        "scope_end_date, pattern, generation_status, generation_error "
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
        'generation_status': row['generation_status'],
        'generation_error': row['generation_error'],
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


def _view_plan_url(plan_version_id: int) -> str:
    return url_for('plan_create.view_plan', plan_version_id=plan_version_id)


def _mark_plan_failed(
    db, plan_version_id: int, user_id: int, message: str
) -> dict:
    """Persist a terminal failure on the plan_versions row + return the
    poller JSON. Rolls back first so the write lands on a clean transaction
    even if an upstream layer left the connection mid-statement."""
    db.rollback()
    db.execute(
        "UPDATE plan_versions SET generation_status = 'failed', "
        "generation_error = ? WHERE id = ? AND user_id = ?",
        (message, plan_version_id, user_id),
    )
    db.commit()
    return {"status": "failed", "error": message}


def _advance_plan_generation(db, uid: int, plan_version_id: int) -> dict:
    """Run one resumable generation pass for plan_versions row
    `plan_version_id`, scoped to `uid`. Shared by the progress-screen
    poller (`generate_plan`) and the background cron
    (`cron_generate_pending`) so generation advances whether the create
    tab is open or closed.

    Returns a view-agnostic outcome dict — no URLs, the caller owns view
    concerns:
      {"status": "not_found"}                   — no such row for this user
      {"status": "ready"}                        — generation complete
      {"status": "failed", "error": <message>}   — typed upstream failure

    Already-terminal rows short-circuit without re-running the cone, so a
    poll (or cron pass) that races a just-finished row is a cheap no-op.
    On a fresh pass each upstream layer + per-phase synthesis is
    individually cached + committed in `layer4_cache`; a pass cut short by
    the function timeout resumes from the cache on the next call rather
    than restarting. On completion the sessions persist atomically
    (DELETE-guarded) and the row flips to `ready`; a typed upstream error
    flips it to `failed`.
    """
    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        return {"status": "not_found"}

    status = plan_version['generation_status']
    if status == 'ready':
        return {"status": "ready"}
    if status == 'failed':
        return {
            "status": "failed",
            "error": plan_version['generation_error']
            or "Plan generation failed. Please try again.",
        }

    try:
        result = orchestrate_plan_create(
            db, uid,
            plan_start_date=plan_version['scope_start_date'],
            plan_version_id=plan_version_id,
            cache=_build_layer4_cache(),
        )
    except OrchestrationError as exc:
        return _mark_plan_failed(
            db, plan_version_id, uid, _orchestration_error_message(exc)
        )
    except (Layer4InputError, Layer4OutputError) as exc:
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Plan synthesis failed ({exc.code}). Adjust your inputs and try again.",
        )
    except (Layer3AOutputError, Layer3BOutputError) as exc:
        return _mark_plan_failed(
            db, plan_version_id, uid,
            f"Athlete evaluation failed ({exc.code}). Try again or contact support.",
        )
    except Exception as exc:
        # Anything not in the typed-error contract (e.g. a DB error mid-cone)
        # must still flip the row to a terminal state — otherwise it escapes as
        # a raw 500 AND the row stays 'generating', so the every-minute cron
        # re-picks it and 500-loops forever, burning a real cone each fire.
        print(
            f"_advance_plan_generation: unexpected {type(exc).__name__} for "
            f"plan_version_id={plan_version_id}: {exc}"
        )
        return _mark_plan_failed(
            db, plan_version_id, uid,
            "Plan generation failed unexpectedly. Please try again or contact support.",
        )

    # Success. DELETE-before-insert keeps the persist idempotent: if a prior
    # pass committed sessions then died before flipping the status, the
    # cache-hit replay would otherwise collide on the natural-key UNIQUE.
    db.execute(
        "DELETE FROM plan_sessions WHERE plan_version_id = ?",
        (plan_version_id,),
    )
    persist_layer4_sessions(db, result)
    db.execute(
        "UPDATE plan_versions SET generation_status = 'ready', "
        "generation_error = NULL WHERE id = ? AND user_id = ?",
        (plan_version_id, uid),
    )
    db.commit()
    return {"status": "ready"}


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route('/new', methods=['GET', 'POST'])
def new_plan():
    """Render the create form on GET. On POST: parse + allocate the
    plan_versions row, mark it 'generating', commit, and redirect to the
    progress screen. The cone runs asynchronously via `generate_plan` —
    the POST itself does no LLM work so it can't blow the function timeout."""
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

        # Don't run the cone here. The full Layer 3A → 3B → per-phase Layer 4
        # cascade is many sequential extended-thinking LLM calls — minutes of
        # wall-clock that blows the serverless function timeout. Mark the row
        # 'generating', commit, and hand off to the progress screen, which
        # drives generation step-by-step via POST /<id>/generate (each pass
        # resumes from the layer4_cache).
        db.execute(
            "UPDATE plan_versions SET generation_status = 'generating' "
            "WHERE id = ? AND user_id = ?",
            (plan_version_id, uid),
        )
        db.commit()
        return redirect(
            url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
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

    status = plan_version['generation_status']
    if status == 'generating':
        return redirect(
            url_for('plan_create.plan_progress', plan_version_id=plan_version_id)
        )
    if status == 'failed':
        flash(
            plan_version['generation_error']
            or "Plan generation failed. Please try again.",
            'danger',
        )
        return redirect(url_for('plan_create.new_plan'))

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


@bp.route('/<int:plan_version_id>/progress', methods=['GET'])
def plan_progress(plan_version_id: int):
    """Render the generation progress screen. Its JS polls
    `generate_plan` until the plan is ready (then redirects to the view)
    or fails (then surfaces the error). A ready plan skips straight to the
    view; a missing/cross-user id 404s via `_load_plan_version`."""
    db = get_db()
    uid = current_user_id()

    plan_version = _load_plan_version(db, uid, plan_version_id)
    if plan_version is None:
        abort(404)

    if plan_version['generation_status'] == 'ready':
        return redirect(_view_plan_url(plan_version_id))

    return render_template(
        'plan_create/progress.html',
        plan_version=plan_version,
        generate_url=url_for(
            'plan_create.generate_plan', plan_version_id=plan_version_id
        ),
        view_url=_view_plan_url(plan_version_id),
        new_url=url_for('plan_create.new_plan'),
    )


@bp.route('/<int:plan_version_id>/generate', methods=['POST'])
def generate_plan(plan_version_id: int):
    """Resumable generation step for the progress poller. Returns JSON.

    Thin wrapper over `_advance_plan_generation` (shared with the
    background cron). Maps the view-agnostic outcome to the poller's JSON:
    a missing/cross-user row 404s; `ready` carries the view redirect;
    `failed` carries the stored error message.
    """
    db = get_db()
    uid = current_user_id()

    outcome = _advance_plan_generation(db, uid, plan_version_id)
    if outcome['status'] == 'not_found':
        abort(404)
    if outcome['status'] == 'ready':
        return jsonify(
            {"status": "ready", "redirect": _view_plan_url(plan_version_id)}
        )
    return jsonify({"status": "failed", "error": outcome['error']})


@bp.route('/cron/generate-pending', methods=['GET'])
def cron_generate_pending():
    """Background generation backstop. Vercel Cron hits this with
    `Authorization: Bearer $CRON_SECRET`; it advances up to
    `_CRON_ADVANCE_BATCH` plan_versions rows still in `generating` by one
    resumable pass each, so a plan finishes even with the create tab
    closed (the progress screen still polls for faster feedback when open).

    Each row is advanced under its own owner's user id + committed
    independently inside `_advance_plan_generation`, so a pass cut short by
    the function timeout keeps the rows it already finished. Returns JSON
    `{advanced: N, ready: R, failed: F}`. Idempotent — already-terminal
    rows are excluded by the WHERE filter, and a row mid-flight resumes
    from `layer4_cache` on the next fire.
    """
    if not cron_authorized():
        abort(401)

    db = get_db()
    rows = db.execute(
        "SELECT id, user_id FROM plan_versions "
        "WHERE generation_status = 'generating' "
        "ORDER BY created_at ASC LIMIT ?",
        (_CRON_ADVANCE_BATCH,),
    ).fetchall()

    advanced = ready = failed = 0
    for row in rows:
        outcome = _advance_plan_generation(db, int(row['user_id']), int(row['id']))
        advanced += 1
        if outcome['status'] == 'ready':
            ready += 1
        elif outcome['status'] == 'failed':
            failed += 1

    return jsonify(advanced=advanced, ready=ready, failed=failed), 200
