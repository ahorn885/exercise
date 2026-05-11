"""COROS integration.

Phase 0: webhook stub only. Returns the COROS success envelope
(`{"result":"0000","message":"ok"}`) for any incoming request so the
partner application can be submitted with a live URL. Real signature
verification and dispatch land in Phase 6, once the partner application
is approved and credentials are issued.

The GET handler exists so any human or validation probe hitting the URL
in a browser gets a 200 instead of a 405.
"""
from flask import Blueprint, jsonify

bp = Blueprint('coros', __name__, url_prefix='/coros')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(result='0000', message='ok'), 200
