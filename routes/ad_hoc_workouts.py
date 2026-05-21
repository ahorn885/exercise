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

D-63 §5.4 T1 plan-check hook + §5.1/§5.2 `is_ad_hoc` extensions on
`cardio_log`/`training_log` defer to the log-this slice (paired with
D-64 caller-side). v1 ships generate + view + discard + regenerate;
[Log this workout] is not wired here.

"Somewhere else" quick-equipment path (D-63 §3.4) deferred to a form-
refresh follow-on. v1 forces locale-only requests.
"""

from __future__ import annotations

import json
from typing import Any

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
        "status, regenerated_into_id "
        "FROM ad_hoc_workout_suggestions "
        "WHERE id = ? AND user_id = ?",
        (suggestion_id, user_id),
    ).fetchone()
    if row is None:
        return None
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
    """Render the generated session card with [Regenerate] + [Discard]
    actions. 404 on miss + cross-user-defense via the user_id filter in
    `_get_suggestion`."""
    db = get_db()
    uid = current_user_id()

    suggestion = _get_suggestion(db, uid, suggestion_id)
    if suggestion is None:
        abort(404)

    return render_template(
        'workouts/suggestion_view.html',
        suggestion=suggestion,
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
