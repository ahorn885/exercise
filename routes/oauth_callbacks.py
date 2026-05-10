"""OAuth provider callback stubs.

Placeholder endpoints so the redirect URIs registered in the Garmin,
Strava, Polar, and Wahoo developer portals resolve to a real route
instead of 404ing during provider-side verification. Each handler
returns 501 until the real OAuth flow is implemented.

Registered URIs (production):
- https://aidstation-pro.vercel.app/auth/garmin/callback
- https://aidstation-pro.vercel.app/auth/strava/callback
- https://aidstation-pro.vercel.app/auth/polar/callback
- https://aidstation-pro.vercel.app/auth/wahoo/callback

These endpoints are added to `_AUTH_EXEMPT_ENDPOINTS` in `app.py` so the
provider can hit them without a logged-in session.
"""
from flask import Blueprint

bp = Blueprint('oauth_callbacks', __name__, url_prefix='/auth')


def _stub(provider: str):
    return (
        f'{provider} OAuth callback not yet implemented.',
        501,
        {'Content-Type': 'text/plain; charset=utf-8'},
    )


@bp.route('/garmin/callback', methods=['GET', 'POST'])
def garmin():
    return _stub('Garmin')


@bp.route('/strava/callback', methods=['GET', 'POST'])
def strava():
    return _stub('Strava')


@bp.route('/polar/callback', methods=['GET', 'POST'])
def polar():
    return _stub('Polar')


@bp.route('/wahoo/callback', methods=['GET', 'POST'])
def wahoo():
    return _stub('Wahoo')
