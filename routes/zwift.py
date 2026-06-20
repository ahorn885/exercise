"""Zwift integration.

Phase 0: webhook stub only. Returns 200 OK for any GET/POST so the URL
checks out if Zwift probes it at form-save. Zwift's public partner API
is OAuth-2.0-based and historically pull-oriented (activity export
after a ride completes); a push channel exists for select partners and
is configured via the developer portal. Real verification and dispatch
land alongside the OAuth connect flow in the matching phase of the
master plan.

Open questions to confirm with Zwift partner support before promotion:
  - Whether a push channel is granted for our partner tier.
  - Auth scheme on incoming pushes (bearer vs. HMAC).
  - Event shape (single activity vs. batch).

Outbound (#681 Wave 3b): Zwift has no push API, so the outbound channel is a
`.zwo` workout file the athlete downloads and drops into their Zwift Workouts
folder. `export_zwo` serializes one cardio plan-session (bike/run only) via
`routes.outbound_workout.to_zwo`. Login-gated by the global auth wall.
"""
from flask import Blueprint, Response, abort, jsonify

from database import get_db
from plan_sessions_repo import load_plan_session_payload
from routes.auth import current_user_id
from routes.outbound_workout import to_zwo

bp = Blueprint('zwift', __name__, url_prefix='/zwift')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200


@bp.route('/export/<int:plan_version_id>/<date>/<int:idx>.zwo')
def export_zwo(plan_version_id: int, date: str, idx: int):
    """Download one cardio plan-session as a Zwift `.zwo` workout file.

    404 if no such session belongs to the user; 400 if the session isn't a
    Zwift-exportable cardio session (non-cardio, or a non-bike/run discipline).
    """
    uid = current_user_id()
    session = load_plan_session_payload(get_db(), uid, plan_version_id, date, idx)
    if session is None:
        print(f"[zwift-export] user={uid} pv={plan_version_id} {date}#{idx} -> 404 not found")
        abort(404)
    try:
        xml = to_zwo(session)
    except ValueError as e:
        print(f"[zwift-export] user={uid} pv={plan_version_id} {date}#{idx} -> 400 {e}")
        abort(400, description=str(e))
    fname = f"aidstation-{date}-{idx}.zwo"
    return Response(
        xml,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'},
    )
