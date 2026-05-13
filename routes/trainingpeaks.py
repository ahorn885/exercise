"""TrainingPeaks integration.

Phase 0: webhook stub only. Returns 200 OK for any GET/POST so the URL
checks out if TrainingPeaks probes it at form-save. TrainingPeaks uses
OAuth 2.0 for the API; the workout-push channel is configured per
partner via their partner portal, and auth on the incoming push is
verified by matching the OAuth bearer the partner-registered service
account sends. Real verification and dispatch land alongside the OAuth
connect flow in the matching phase of the master plan.

Open questions to confirm with TP partner support before promotion:
  - Exact push auth scheme (bearer vs. basic vs. shared secret).
  - Whether the push body is a single event or a batch.
  - Retry / dedupe behavior on non-2xx responses.
"""
from flask import Blueprint, jsonify

bp = Blueprint('trainingpeaks', __name__, url_prefix='/trainingpeaks')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200
