"""OAuth provider callback stubs.

Placeholder endpoints so the redirect URIs registered in each provider's
developer portal resolve to a real route instead of 404ing during
provider-side verification. Each provider returns 501 until the real
OAuth exchange is implemented.

Adding a new provider:
  1. Append a `(slug, display_name)` tuple to `_PROVIDERS` below.
  2. Register `https://aidstation-pro.vercel.app/auth/<slug>/callback`
     in the provider's developer portal.

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
_PROVIDERS: tuple[tuple[str, str], ...] = (
    # Wave 1 — initial integrations
    ('garmin',          'Garmin'),
    ('strava',          'Strava'),
    ('polar',           'Polar'),
    ('wahoo',           'Wahoo'),
    # Wave 2 — added 2026-05-11
    ('coros',           'COROS'),
    ('google-health',   'Google Health'),
    ('apple-health',    'Apple Health'),
    ('whoop',           'Whoop'),
    ('trainingpeaks',   'TrainingPeaks'),
    ('zwift',           'Zwift'),
    ('vo2',             'V.02'),
    ('nike-run-club',   'Nike Run Club'),
    ('ride-with-gps',   'Ride With GPS'),
    ('decathlon',       'Decathlon'),
    ('adidas-running',  'adidas Running'),
    ('komoot',          'Komoot'),
    ('final-surge',     'Final Surge'),
    ('myfitnesspal',    'MyFitnessPal'),
)
_PROVIDER_NAMES = dict(_PROVIDERS)


@bp.route('/<provider>/callback', methods=['GET', 'POST'])
def callback(provider: str):
    name = _PROVIDER_NAMES.get(provider)
    if name is None:
        abort(404)
    return (
        f'{name} OAuth callback not yet implemented.',
        501,
        {'Content-Type': 'text/plain; charset=utf-8'},
    )


def provider_slugs() -> tuple[str, ...]:
    """Public accessor — used by the wellness page footer to enumerate
    registered providers without re-declaring the list."""
    return tuple(slug for slug, _ in _PROVIDERS)
