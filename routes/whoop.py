"""Whoop integration.

Phase 0: webhook stub only. Returns 200 OK for any GET/POST so the URL
checks out if Whoop probes it at form-save. Real verification (HMAC-
SHA256 over the raw body with the client secret, base64-encoded in the
`X-WHOOP-Signature` header, plus the `X-WHOOP-Signature-Timestamp`
window check) and dispatch of the event payload (`user_id`, `id`,
`type` e.g. `workout.updated`, `trace_id`) land alongside the OAuth
connect flow in the matching phase of the master plan.

The signing key is `WHOOP_CLIENT_SECRET` — same secret used for OAuth
token exchange, per Whoop's single-credential model.
"""
from flask import Blueprint, jsonify

bp = Blueprint('whoop', __name__, url_prefix='/whoop')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200
