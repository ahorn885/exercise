"""Strava integration.

Phase 0: webhook stub only. Strava push subscriptions use the
Stripe/Slack-style verification handshake: when we eventually POST to
their `/push_subscriptions` API, Strava immediately GETs this URL with
`hub.mode=subscribe`, `hub.verify_token=<our token>`, and
`hub.challenge=<their token>`, and expects a JSON body
`{"hub.challenge": "<their token>"}` — otherwise the subscription is
rejected. The handshake is baked in here so the stub already works the
day we create the subscription; before that, GETs without the query
params and POST events just return 200.

Real event dispatch (aspect_type create/update/delete, object_type
activity/athlete) and `webhook_events` recording land alongside the
OAuth connect flow in Phase 1 of the master plan. Strava events carry
no signature — auth is by `subscription_id` match against the one
subscription we own.
"""
from flask import Blueprint, jsonify, request

bp = Blueprint('strava', __name__, url_prefix='/strava')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        challenge = request.args.get('hub.challenge')
        if challenge is not None:
            return jsonify({'hub.challenge': challenge}), 200
        return jsonify(status='ok'), 200
    return jsonify(status='ok'), 200
