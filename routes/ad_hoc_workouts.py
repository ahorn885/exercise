"""D-63 on-demand workout caller-side route (Phase 5.2 caller-side).

Composes `orchestrate_single_session_synthesize` end-to-end:
1. GET `/workouts/build` renders the request form.
2. POST `/workouts/build` allocates a row in `ad_hoc_workout_suggestions`
   with the parsed `SingleSessionRequest` as `request_payload`, invokes
   `orchestrate_single_session_synthesize(... suggestion_id=row_id)`,
   writes the returned `Layer4Payload.sessions[0]` JSON into
   `generated_session`, commits, redirects to the suggestion view.
3. GET `/workouts/suggestions/<id>` renders the generated session.
4. POST `/workouts/suggestions/<id>/discard` marks the row `discarded`.
5. POST `/workouts/suggestions/<id>/regenerate` re-invokes the
   orchestrator with the original `request_payload`, allocates a new
   row, links the old row via `regenerated_into_id` + flips its status
   to `regenerated`, redirects to the new suggestion's view.

Caller owns the transaction per the substrate D-64 §6.2 contract — the
route commits once the orchestrator + persistence both succeed. On
`OrchestrationError` / `Layer4InputError` / `Layer4OutputError`, no
commit fires (the connection's auto-rollback on close keeps the
half-allocated row out of the table; `flash()` + redirect surfaces the
failure to the athlete).

D-63 §5.1/§5.2/§3.5 log-this slice + T1 plan-check hook now wired:
[Log this workout] persists the generated session into cardio_log or
training_log (per `session.kind`) tagged with `is_ad_hoc=TRUE` +
`ad_hoc_suggestion_id`; on success the route redirects back to
`/workouts/suggestions/<id>?just_logged=1` so the post-log T1 hook
modal auto-opens. The modal's [Yes — refresh] links to
`/plans/v2/refresh?nl_context=<auto-filled>&tier=T1`; [No, thanks]
POSTs to the dismiss endpoint that records a `t1_hook_telemetry` row
per §3.5.

"Somewhere else" quick-equipment path (D-63 §3.4) deferred to a form-
refresh follow-on. v1 forces locale-only requests.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import urlencode

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from database import get_db
from layer4 import (
    Layer4Cache,
    OrchestrationError,
    PostgresCacheBackend,
    orchestrate_single_session_synthesize,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.single_session import SingleSessionRequest
from pydantic import ValidationError
from routes.auth import current_user_id
from routes.locales import athlete_locale_choices


bp = Blueprint('ad_hoc_workouts', __name__, url_prefix='/workouts')


VALID_INTENSITIES = ('easy', 'moderate', 'hard', 'race_pace')


# ─── Helpers ────────────────────────────────────────────────────────────────


def _athlete_sport_choices(db) -> list[str]:
    """Broad framework_sport list from `layer0.sports`. Filtered to active
    rows only. v1 is athlete-agnostic — the athlete's primary discipline
    set + cross-training options filter is a v2 follow-on per D-63 §3.2.
    """
    rows = db.execute(
        "SELECT DISTINCT framework_sport FROM layer0.sports "
        "WHERE superseded_at IS NULL "
        "ORDER BY framework_sport"
    ).fetchall()
    return [r['framework_sport'] for r in rows if r['framework_sport']]


def _allocate_suggestion(db, user_id: int, request_payload: dict) -> int:
    """INSERT a `suggested`-status row carrying the SingleSessionRequest
    JSON. Returns the new row id. Caller commits."""
    cur = db.execute(
        "INSERT INTO ad_hoc_workout_suggestions "
        "(user_id, request_payload) VALUES (?, ?) RETURNING id",
        (user_id, json.dumps(request_payload)),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "INSERT INTO ad_hoc_workout_suggestions RETURNING id returned no row"
        )
    return int(row['id'])


def _persist_generated_session(db, suggestion_id: int, session_json: str) -> None:
    """UPDATE the suggestion row with the single generated session JSON.
    Stores the raw `PlanSession.model_dump_json()` so re-hydration works
    via `PlanSession.model_validate_json(...)`."""
    db.execute(
        "UPDATE ad_hoc_workout_suggestions SET generated_session = ? "
        "WHERE id = ?",
        (session_json, suggestion_id),
    )


def _get_suggestion(db, user_id: int, suggestion_id: int) -> dict | None:
    """Fetch a suggestion row by id, scoped to user_id. Returns dict or
    None on miss. JSONB columns are decoded inline; psycopg2 native dict
    pass-through; SQLite-shim JSON-string parsed."""
    row = db.execute(
        "SELECT id, user_id, requested_at, request_payload, generated_session, "
        "status, regenerated_into_id, logged_into_table, logged_into_id "
        "FROM ad_hoc_workout_suggestions "
        "WHERE id = ? AND user_id = ?",
        (suggestion_id, user_id),
    ).fetchone()
    if row is None:
        return None
    logged_into_id_raw = row.get('logged_into_id') if hasattr(row, 'get') else None
    return {
        'id': int(row['id']),
        'user_id': int(row['user_id']),
        'requested_at': row['requested_at'],
        'request_payload': _decode_jsonb(row['request_payload']),
        'generated_session': _decode_jsonb(row['generated_session']) if row['generated_session'] else None,
        'status': row['status'],
        'regenerated_into_id': (
            int(row['regenerated_into_id']) if row['regenerated_into_id'] else None
        ),
        'logged_into_table': row.get('logged_into_table') if hasattr(row, 'get') else None,
        'logged_into_id': int(logged_into_id_raw) if logged_into_id_raw else None,
    }


def _mark_status(
    db,
    suggestion_id: int,
    user_id: int,
    *,
    status: str,
    regenerated_into_id: int | None = None,
) -> None:
    """Flip a suggestion's status, optionally setting `regenerated_into_id`.
    Scoped to user_id defensively."""
    if status == 'discarded':
        db.execute(
            "UPDATE ad_hoc_workout_suggestions "
            "SET status = ?, discarded_at = NOW() "
            "WHERE id = ? AND user_id = ?",
            (status, suggestion_id, user_id),
        )
    elif status == 'regenerated':
        db.execute(
            "UPDATE ad_hoc_workout_suggestions "
            "SET status = ?, regenerated_into_id = ? "
            "WHERE id = ? AND user_id = ?",
            (status, regenerated_into_id, suggestion_id, user_id),
        )
    else:
        raise ValueError(f"_mark_status only handles discarded/regenerated, got {status!r}")


def _decode_jsonb(raw: Any) -> Any:
    """Hydrate a JSONB column tolerantly. psycopg2 returns Python objects;
    SQLite shim returns a JSON string. None passes through."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise TypeError(f"unexpected JSONB payload type: {type(raw).__name__}")


def _build_layer4_cache() -> Layer4Cache:
    """Construct the Layer 4 cache wired to the per-request DB connection.
    Production deployments share the request connection via the factory."""
    return Layer4Cache(PostgresCacheBackend(lambda: get_db()))


def _parse_request_form(form) -> tuple[SingleSessionRequest | None, str | None]:
    """Parse the build-form POST into a SingleSessionRequest. Returns
    (request, None) on success or (None, error_msg) on failure."""
    sport = (form.get('sport') or '').strip()
    duration_raw = (form.get('duration_min') or '').strip()
    intensity = (form.get('intensity') or '').strip()
    locale_slug = (form.get('locale_slug') or '').strip()
    notes_raw = (form.get('notes_for_synthesizer') or '').strip()

    if not sport:
        return None, "Pick a sport."
    if not locale_slug:
        return None, "Pick a location."
    if intensity not in VALID_INTENSITIES:
        return None, "Pick an intensity (easy / moderate / hard / race pace)."
    try:
        duration_min = int(duration_raw)
    except ValueError:
        return None, "Duration must be a whole number of minutes (30–360)."

    try:
        request_obj = SingleSessionRequest(
            sport=sport,
            duration_min=duration_min,
            intensity=intensity,  # type: ignore[arg-type]
            locale_slug=locale_slug,
            notes_for_synthesizer=notes_raw or None,
        )
    except ValidationError as exc:
        return None, f"Invalid request: {exc.errors()[0]['msg']}"
    return request_obj, None


_ORCH_ERROR_MESSAGES = {
    'request_sport_unavailable': "That sport isn't configured in the platform yet. Pick another.",
    'locale_unknown': "That location doesn't match one of your saved locales. Pick another.",
    'etl_version_set_undiscoverable': "Platform data is unavailable. Try again shortly.",
    'framework_sport_missing': "Set your primary sport in your profile before generating a workout.",
}


def _orchestration_error_message(err: OrchestrationError) -> str:
    return _ORCH_ERROR_MESSAGES.get(
        err.code,
        f"Workout generation failed ({err.code}). Try again or contact support.",
    )


# ─── D-63 §5.1/§5.2/§3.5 — log-this slice helpers ───────────────────────────


def _render_nl_context(request_payload: dict, generated_session: dict | None) -> str:
    """Auto-fill NL context string for the post-log T1 hook per D-63 §3.5.

    Template: 'Did an unscheduled {N}min {sport} ({intensity}) at {locale}'.
    Intensity word renders verbatim from the request ('easy' / 'moderate'
    / 'hard' / 'race pace'); the underscore in 'race_pace' renders as a
    space. Locale prefers the generated session's `locale_name` (human-
    readable) over `locale_id` over the request's `locale_slug`, matching
    the precedence used in templates/workouts/suggestion_view.html.
    """
    sport = (request_payload.get('sport') or 'workout').strip()
    duration_min = request_payload.get('duration_min') or 0
    raw_intensity = (request_payload.get('intensity') or '').strip()
    intensity_label = raw_intensity.replace('_', ' ') if raw_intensity else None

    locale = None
    if generated_session:
        locale = generated_session.get('locale_name') or generated_session.get('locale_id')
    locale = locale or (request_payload.get('locale_slug') or 'home')

    if intensity_label:
        return f"Did an unscheduled {duration_min}min {sport} ({intensity_label}) at {locale}"
    return f"Did an unscheduled {duration_min}min {sport} at {locale}"


def _log_cardio_session(
    db,
    user_id: int,
    suggestion_id: int,
    request_payload: dict,
    session: dict,
    *,
    today: date,
) -> int:
    """INSERT one cardio_log row tagged is_ad_hoc=TRUE. Returns new row id.
    Caller owns the transaction. Notes column concatenates the coaching
    intent + session notes from the generated session so the log row
    carries the synthesizer rationale alongside the duration/activity."""
    sport = (request_payload.get('sport') or 'Workout').strip()
    duration_min = float(session.get('duration_min') or 0)
    notes_parts: list[str] = []
    intent = (session.get('coaching_intent') or '').strip()
    sess_notes = (session.get('session_notes') or '').strip()
    if intent:
        notes_parts.append(intent)
    if sess_notes:
        notes_parts.append(sess_notes)
    notes = '\n\n'.join(notes_parts) or None

    cur = db.execute(
        "INSERT INTO cardio_log "
        "(user_id, date, activity, duration_min, notes, "
        "is_ad_hoc, ad_hoc_suggestion_id, ad_hoc_request_payload) "
        "VALUES (?, ?, ?, ?, ?, TRUE, ?, ?) RETURNING id",
        (
            user_id,
            today.isoformat(),
            sport,
            duration_min,
            notes,
            suggestion_id,
            json.dumps(request_payload),
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("INSERT INTO cardio_log RETURNING id returned no row")
    return int(row['id'])


def _log_strength_session(
    db,
    user_id: int,
    suggestion_id: int,
    request_payload: dict,
    session: dict,
    *,
    today: date,
) -> int:
    """INSERT one training_log row per StrengthExercise. Returns the first
    new row's id (used as the canonical logged_into_id on the suggestion
    row — the FK identifies the entry point into the log set; downstream
    queries find all rows in the set via ad_hoc_suggestion_id). Caller
    owns the transaction.

    reps_per_set is `int | str` on the model (e.g. '10-12' for ranges); the
    legacy training_log.target_reps is INTEGER, so range-valued prescriptions
    persist into notes only.
    """
    exercises = session.get('strength_exercises') or []
    if not exercises:
        raise ValueError("strength session has no strength_exercises to log")
    first_row_id: int | None = None
    request_payload_json = json.dumps(request_payload)
    today_iso = today.isoformat()
    for ex in exercises:
        reps_raw = ex.get('reps_per_set')
        target_reps = int(reps_raw) if isinstance(reps_raw, int) else None
        notes_parts: list[str] = []
        load = (ex.get('load_prescription') or '').strip()
        tempo = (ex.get('tempo') or '').strip()
        instructions = (ex.get('instructions') or '').strip()
        if load:
            notes_parts.append(f"Load: {load}")
        if tempo:
            notes_parts.append(f"Tempo: {tempo}")
        if isinstance(reps_raw, str) and reps_raw:
            notes_parts.append(f"Reps: {reps_raw}")
        if instructions:
            notes_parts.append(instructions)
        notes = '\n'.join(notes_parts) or None
        cur = db.execute(
            "INSERT INTO training_log "
            "(user_id, date, exercise, target_sets, target_reps, rest_sec, notes, "
            "is_ad_hoc, ad_hoc_suggestion_id, ad_hoc_request_payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, TRUE, ?, ?) RETURNING id",
            (
                user_id,
                today_iso,
                ex.get('exercise_name') or 'Strength exercise',
                ex.get('sets'),
                target_reps,
                ex.get('rest_between_sets_sec'),
                notes,
                suggestion_id,
                request_payload_json,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("INSERT INTO training_log RETURNING id returned no row")
        if first_row_id is None:
            first_row_id = int(row['id'])
    assert first_row_id is not None
    return first_row_id


def _mark_logged(
    db,
    suggestion_id: int,
    user_id: int,
    *,
    logged_into_table: str,
    logged_into_id: int,
) -> None:
    """Flip the suggestion's status to 'logged' + populate the logged_into_*
    pointers per D-63 §5.5. Scoped to user_id. Caller owns the transaction."""
    db.execute(
        "UPDATE ad_hoc_workout_suggestions "
        "SET status = 'logged', logged_into_table = ?, logged_into_id = ? "
        "WHERE id = ? AND user_id = ?",
        (logged_into_table, logged_into_id, suggestion_id, user_id),
    )


def _record_t1_dismiss(db, user_id: int, suggestion_id: int) -> None:
    """INSERT one t1_hook_telemetry row recording a [No, thanks] dismissal
    of the post-log T1 plan-check hook per D-63 §3.5. Caller commits."""
    db.execute(
        "INSERT INTO t1_hook_telemetry (user_id, suggestion_id) VALUES (?, ?)",
        (user_id, suggestion_id),
    )


# ─── Routes ─────────────────────────────────────────────────────────────────


@bp.route('/build', methods=['GET', 'POST'])
def build_workout():
    """Render the build form on GET; allocate suggestion + invoke
    orchestrator + persist generated session on POST. Atomic per D-64 §6.2:
    commit fires only after both allocate + orchestrate + persist succeed.
    """
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        req_obj, err = _parse_request_form(request.form)
        if err is not None or req_obj is None:
            flash(err or "Invalid input.", 'danger')
            return redirect(url_for('ad_hoc_workouts.build_workout'))

        request_payload = req_obj.model_dump(mode='json')

        suggestion_id = _allocate_suggestion(db, uid, request_payload)
        try:
            result = orchestrate_single_session_synthesize(
                db, uid, req_obj, suggestion_id,
                cache=_build_layer4_cache(),
            )
        except OrchestrationError as exc:
            flash(_orchestration_error_message(exc), 'danger')
            return redirect(url_for('ad_hoc_workouts.build_workout'))
        except (Layer4InputError, Layer4OutputError) as exc:
            flash(f"Workout synthesis failed ({exc.code}). Pick different inputs and retry.", 'danger')
            return redirect(url_for('ad_hoc_workouts.build_workout'))

        _persist_generated_session(
            db, suggestion_id, result.sessions[0].model_dump_json()
        )
        db.commit()
        return redirect(
            url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id)
        )

    sport_choices = _athlete_sport_choices(db)
    locale_choices = athlete_locale_choices(db, uid)
    return render_template(
        'workouts/build_form.html',
        sport_choices=sport_choices,
        locale_choices=locale_choices,
        intensities=VALID_INTENSITIES,
    )


@bp.route('/suggestions/<int:suggestion_id>', methods=['GET'])
def view_suggestion(suggestion_id: int):
    """Render the generated session card with [Log this workout] +
    [Regenerate] + [Discard] actions. 404 on miss + cross-user-defense
    via the user_id filter in `_get_suggestion`.

    When `?just_logged=1` is on the query string the template renders the
    post-log T1 plan-check hook modal and auto-opens it on page load per
    D-63 §3.5. The auto-fill NL context for the [Yes — refresh] anchor
    is computed server-side from the suggestion's request_payload +
    generated_session so it stays deterministic across re-renders."""
    db = get_db()
    uid = current_user_id()

    suggestion = _get_suggestion(db, uid, suggestion_id)
    if suggestion is None:
        abort(404)

    just_logged = request.args.get('just_logged') == '1'
    t1_hook_nl_context = _render_nl_context(
        suggestion['request_payload'], suggestion['generated_session']
    )
    t1_hook_refresh_query = urlencode({
        'nl_context': t1_hook_nl_context, 'tier': 'T1',
    })

    return render_template(
        'workouts/suggestion_view.html',
        suggestion=suggestion,
        just_logged=just_logged,
        t1_hook_nl_context=t1_hook_nl_context,
        t1_hook_refresh_query=t1_hook_refresh_query,
    )


@bp.route('/suggestions/<int:suggestion_id>/log', methods=['POST'])
def log_suggestion(suggestion_id: int):
    """Persist the suggestion's generated_session into cardio_log or
    training_log (per session.kind), flip suggestion.status='logged' +
    populate logged_into_table/id, commit atomically per D-64 §6.2.
    Redirects back to the suggestion view with ?just_logged=1 so the
    T1 hook modal auto-opens per D-63 §3.5."""
    db = get_db()
    uid = current_user_id()

    suggestion = _get_suggestion(db, uid, suggestion_id)
    if suggestion is None:
        abort(404)

    if suggestion['status'] != 'suggested':
        flash("This workout has already been logged, discarded, or regenerated.", 'warning')
        return redirect(url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id))

    session = suggestion.get('generated_session')
    if session is None:
        flash("This workout was not generated; nothing to log.", 'danger')
        return redirect(url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id))

    kind = session.get('kind')
    today = date.today()
    try:
        if kind == 'cardio':
            log_id = _log_cardio_session(
                db, uid, suggestion_id,
                request_payload=suggestion['request_payload'],
                session=session, today=today,
            )
            logged_into_table = 'cardio_log'
        elif kind == 'strength':
            log_id = _log_strength_session(
                db, uid, suggestion_id,
                request_payload=suggestion['request_payload'],
                session=session, today=today,
            )
            logged_into_table = 'training_log'
        else:
            flash(f"Can't log sessions of kind {kind!r}.", 'danger')
            return redirect(url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id))
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        flash(f"Could not log the workout: {exc}", 'danger')
        return redirect(url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id))

    _mark_logged(
        db, suggestion_id, uid,
        logged_into_table=logged_into_table, logged_into_id=log_id,
    )
    db.commit()
    return redirect(
        url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id)
        + '?just_logged=1'
    )


@bp.route('/suggestions/<int:suggestion_id>/dismiss_t1_hook', methods=['POST'])
def dismiss_t1_hook(suggestion_id: int):
    """Record a [No, thanks] dismissal of the post-log T1 plan-check hook
    per D-63 §3.5. Redirects back to the suggestion view (the modal
    does NOT re-open since the redirect drops ?just_logged=1)."""
    db = get_db()
    uid = current_user_id()

    suggestion = _get_suggestion(db, uid, suggestion_id)
    if suggestion is None:
        abort(404)

    _record_t1_dismiss(db, uid, suggestion_id)
    db.commit()
    return redirect(
        url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id)
    )


@bp.route('/suggestions/<int:suggestion_id>/discard', methods=['POST'])
def discard_suggestion(suggestion_id: int):
    """Flip the suggestion's status to `discarded`. Commits."""
    db = get_db()
    uid = current_user_id()

    suggestion = _get_suggestion(db, uid, suggestion_id)
    if suggestion is None:
        abort(404)

    _mark_status(db, suggestion_id, uid, status='discarded')
    db.commit()
    flash("Discarded.", 'info')
    return redirect(url_for('ad_hoc_workouts.build_workout'))


@bp.route('/suggestions/<int:suggestion_id>/regenerate', methods=['POST'])
def regenerate_suggestion(suggestion_id: int):
    """Re-run the orchestrator with the original request_payload, link the
    new row via `regenerated_into_id` on the prior row, flip the prior
    row to `regenerated` status. Atomic per D-64 §6.2: commit fires only
    after both rows land + orchestrator succeeds."""
    db = get_db()
    uid = current_user_id()

    prior = _get_suggestion(db, uid, suggestion_id)
    if prior is None:
        abort(404)

    try:
        req_obj = SingleSessionRequest(**prior['request_payload'])
    except ValidationError as exc:
        flash(f"Original request payload is no longer valid ({exc.errors()[0]['msg']}). Start a new request.", 'danger')
        return redirect(url_for('ad_hoc_workouts.build_workout'))

    new_suggestion_id = _allocate_suggestion(db, uid, prior['request_payload'])
    try:
        result = orchestrate_single_session_synthesize(
            db, uid, req_obj, new_suggestion_id,
            cache=_build_layer4_cache(),
        )
    except OrchestrationError as exc:
        flash(_orchestration_error_message(exc), 'danger')
        return redirect(
            url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id)
        )
    except (Layer4InputError, Layer4OutputError) as exc:
        flash(f"Workout synthesis failed ({exc.code}).", 'danger')
        return redirect(
            url_for('ad_hoc_workouts.view_suggestion', suggestion_id=suggestion_id)
        )

    _persist_generated_session(
        db, new_suggestion_id, result.sessions[0].model_dump_json()
    )
    _mark_status(
        db, suggestion_id, uid,
        status='regenerated',
        regenerated_into_id=new_suggestion_id,
    )
    db.commit()
    return redirect(
        url_for('ad_hoc_workouts.view_suggestion', suggestion_id=new_suggestion_id)
    )
