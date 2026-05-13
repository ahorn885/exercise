"""Ride With GPS integration.

Phase 0: webhook stub only. Returns 200 OK for any GET/POST so the URL
checks out if RWGPS probes it. Real HMAC-SHA256 verification (using
`x-rwgps-signature` and the API client secret), batch dispatch of the
`notifications[]` array, and `webhook_events` recording land later
alongside the OAuth connect flow.

RWGPS requires a 200 response within 1 second per their docs. There is
no retry — failed deliveries are lost — so when we promote this from a
stub, the handler must ack immediately and defer processing.
"""
from flask import Blueprint, jsonify

bp = Blueprint('ride_with_gps', __name__, url_prefix='/ride-with-gps')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200
