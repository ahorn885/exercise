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
"""
from flask import Blueprint, jsonify

bp = Blueprint('zwift', __name__, url_prefix='/zwift')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200
