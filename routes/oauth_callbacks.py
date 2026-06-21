"""OAuth provider callback stubs.

Placeholder endpoints so the redirect URIs registered in each provider's
developer portal resolve to a real route instead of 404ing during
provider-side verification. Each provider returns 501 until the real
OAuth exchange is implemented.

Adding a new STUB provider:
  1. Append a `(slug, display_name)` tuple to `_PROVIDERS` below.
  2. Register `https://aidstation-pro.vercel.app/auth/<slug>/callback`
     in the provider's developer portal.

Promoting a stub to a REAL OAuth flow (IMPORTANT — read this):
  A real provider blueprint owns its own callback at
  `/<slug>/oauth/callback` (see routes/wahoo.py, routes/strava.py, …).
  When you ship one you MUST:
    1. REMOVE the `(slug, …)` tuple from `_PROVIDERS` here, and
    2. register the developer-portal redirect_uri as
       `https://aidstation-pro.vercel.app/<slug>/oauth/callback`
       — NOT `/auth/<slug>/callback`.
  If you skip step 1 the dead stub keeps answering `/auth/<slug>/callback`
  and this docstring keeps advertising the wrong redirect_uri, so whoever
  configures the portal registers a URI the live flow never sends to.
  Wahoo `oauth_start` sends `…/wahoo/oauth/callback`; if the portal has
  `…/auth/wahoo/callback`, the provider rejects the request right after
  the user logs in (redirect_uri mismatch). That class of bug is exactly
  why COROS/Polar/Strava/Whoop/Wahoo/Oura/Ride With GPS are NOT below.

The single endpoint name `oauth_callbacks.callback` is in
`_AUTH_EXEMPT_ENDPOINTS` in `app.py`, so all current and future provider
slugs are exempt without any further wiring.
"""
from flask import Blueprint, abort

bp = Blueprint('oauth_callbacks', __name__, url_prefix='/auth')


# (slug, display_name). slug must be URL-safe (lowercase, hyphenated).
# display_name is shown in the 501 body and is the only place a
# brand-correct spelling lives — keep it canonical (e.g. "adidas Running"
# is intentionally lowercase-a, "V.02" keeps the period).
#
# NOT here (real OAuth flows own their own /<slug>/oauth/callback; their
# developer-portal redirect_uri must point at that real path):
#   COROS        → /coros/oauth/callback        (routes/coros.py)
#   Polar        → /polar/oauth/callback        (routes/polar.py)
#   Strava       → /strava/oauth/callback       (routes/strava.py)
#   Whoop        → /whoop/oauth/callback        (routes/whoop.py)
#   Wahoo        → /wahoo/oauth/callback        (routes/wahoo.py)
#   Oura         → /oura/oauth/callback         (routes/oura.py)
#   Ride With GPS→ /ride-with-gps/oauth/callback (routes/ride_with_gps.py)
# (Strava/Whoop/Wahoo/Oura/RWGPS were promoted in #681 (B)/PR #799 but left
#  stale below until now; COROS/Polar were removed earlier in PR1/PR3.)
_PROVIDERS: tuple[tuple[str, str], ...] = (
    # Genuine stubs only — no real OAuth exchange yet.
    ('garmin',          'Garmin'),
    ('google-health',   'Google Health'),
    ('apple-health',    'Apple Health'),
    ('trainingpeaks',   'TrainingPeaks'),
    ('zwift',           'Zwift'),
    ('vo2',             'V.02'),
    ('nike-run-club',   'Nike Run Club'),
    ('decathlon',       'Decathlon'),
    ('adidas-running',  'adidas Running'),
    ('komoot',          'Komoot'),
    ('final-surge',     'Final Surge'),
    ('myfitnesspal',    'MyFitnessPal'),
)
_PROVIDER_NAMES = dict(_PROVIDERS)

# Providers whose developer portal HEAD- or GET-probes the registered
# redirect URI when the partner saves the API-client form. For these we
# return 200 instead of 501 so the form-side validation passes. Once the
# real OAuth exchange ships, the provider drops out of this set.
_PROBED_AT_REGISTRATION: frozenset[str] = frozenset({
    'trainingpeaks',
    'zwift',
})


@bp.route('/<provider>/callback', methods=['GET', 'POST'])
def callback(provider: str):
    name = _PROVIDER_NAMES.get(provider)
    if name is None:
        abort(404)
    body = f'{name} OAuth callback not yet implemented.'
    status = 200 if provider in _PROBED_AT_REGISTRATION else 501
    return (body, status, {'Content-Type': 'text/plain; charset=utf-8'})


def provider_slugs() -> tuple[str, ...]:
    """Public accessor — used by the wellness page footer to enumerate
    registered providers without re-declaring the list."""
    return tuple(slug for slug, _ in _PROVIDERS)
