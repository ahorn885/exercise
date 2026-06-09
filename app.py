import os
import re as _re
import secrets as _secrets
from datetime import datetime, timezone
from urllib.parse import quote as _urlquote
from flask import Flask, request, redirect, url_for, session, g, render_template
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import init_app, get_db

app = Flask(__name__, instance_relative_config=True)

# SECRET_KEY is mandatory: Flask session cookies are signed with it, so a
# predictable value lets anyone forge a session for any user. Refuse to
# boot without it rather than fall back to a hardcoded default.
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    raise RuntimeError(
        'SECRET_KEY environment variable is required. Generate one with '
        '`python -c "import secrets; print(secrets.token_urlsafe(48))"` and '
        'set it on every deploy target before starting the app.'
    )
app.secret_key = _secret

# SECRET_KEY_FALLBACKS lets us rotate SECRET_KEY without bouncing every
# logged-in user. Set SECRET_KEY to the new value and SECRET_KEY_FALLBACK
# to the old one; Flask signs new cookies with the new key but verifies
# against either, so existing sessions keep working until they expire or
# the fallback is dropped. Comma-separated for multi-step rotations.
_fallbacks = [
    s.strip() for s in (os.environ.get('SECRET_KEY_FALLBACK', '') or '').split(',')
    if s.strip()
]
if _fallbacks:
    app.config['SECRET_KEY_FALLBACKS'] = _fallbacks

# Session cookie hardening. SECURE defaults on when the deploy looks
# HTTPS-fronted (Vercel sets DATABASE_URL; local dev over HTTP doesn't).
# Override explicitly via SESSION_COOKIE_SECURE=0/1 if needed.
def _envbool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ('0', 'false', 'no', 'off', '')

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = _envbool(
    'SESSION_COOKIE_SECURE', default=bool(os.environ.get('DATABASE_URL'))
)

# Postgres — auto-migrate schema on every cold start. All statements use
# IF NOT EXISTS so this is safe to run repeatedly.
from init_db import init_postgres
try:
    init_postgres()
except Exception as _e:
    print(f'Warning: DB init skipped: {_e}')

init_app(app)

# CSRF protection on every state-changing form/JSON POST. Flask-WTF reads the
# token from a `csrf_token` form field or an `X-CSRFToken` header. JSON
# fetches from JS rely on the header — see static/app.js, which wraps
# window.fetch to inject it from the <meta name="csrf-token"> tag.
csrf = CSRFProtect(app)


@app.errorhandler(CSRFError)
def _handle_csrf_error(e):
    # Render a plain message rather than the default HTML — keeps responses
    # uniform regardless of whether the caller is a browser form or a JS
    # fetch. 400 (not 403) matches Flask-WTF's default.
    return (f'CSRF validation failed: {e.description}', 400)


# ── Trail-voice error pages (redesign §27) ───────────────────────────────────
# Shared `_error.html` rendered by the 404 + 500 handlers. The page is
# standalone (no shell includes) so a 500 can't cascade while rendering its own
# error page. Each carries a per-request diagnostic block; the "Email help"
# button is a mailto: with that diagnostic pre-filled (the user copies nothing).
def _error_request_id() -> str:
    return 'req_' + _secrets.token_hex(5)


def _error_mailto(code: str, diag: list[tuple[str, str]]) -> str:
    subject = f'AIDSTATION error · {code}'
    body = '\n'.join(
        ['Hi — I hit an error in AIDSTATION. The diagnostic below was pre-filled:', '']
        + [f'{k}: {v}' for k, v in diag]
    )
    return (
        f'mailto:help@aidstation.pro'
        f'?subject={_urlquote(subject)}&body={_urlquote(body)}'
    )


@app.errorhandler(404)
def _handle_404(e):
    code = '404 · NO SUCH ROUTE'
    diag = [
        ('request_id', _error_request_id()),
        ('attempted_path', request.path),
        ('method', request.method),
        ('status', '404 not_found'),
    ]
    return render_template(
        '_error.html', tone='bad', glyph='x', code=code,
        title="You're off trail.",
        message="This route isn't on the map — maybe an old link, or a plan "
                "version that's since been archived. No harm done. Here's the "
                "way back.",
        diag=diag, quicklinks=True, show_retry=False,
        mailto_href=_error_mailto(code, diag),
    ), 404


@app.errorhandler(403)
def _handle_403(e):
    code = '403 · ADMIN ONLY'
    diag = [
        ('request_id', _error_request_id()),
        ('attempted_path', request.path),
        ('method', request.method),
        ('status', '403 forbidden'),
    ]
    return render_template(
        '_error.html', tone='warn', glyph='gear', code=code,
        title='Crew only past here.',
        message="This corner of AIDSTATION is admin-only and your account "
                "doesn't have the keys. If that's a surprise, the request_id "
                "below helps us look into it. Here's the way back.",
        diag=diag, quicklinks=True, show_retry=False,
        mailto_href=_error_mailto(code, diag),
    ), 403


@app.errorhandler(500)
def _handle_500(e):
    code = '500 · SOMETHING BROKE'
    orig = getattr(e, 'original_exception', None) or e
    diag = [
        ('request_id', _error_request_id()),
        ('action', f'{request.method} {request.path}'),
        ('status', '500 internal_error'),
        ('timestamp', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')),
    ]
    # The user only ever sees the request_id; the real exception goes to the
    # server log so a support email's request_id can be traced back to it.
    app.logger.error(
        '[error:%s] 500 on %s %s: %r',
        diag[0][1], request.method, request.path, orig,
    )
    # A failed POST can't be safely re-driven by a GET, so "Try again" only
    # reloads the path for GETs; otherwise it routes home.
    retry_href = request.path if request.method == 'GET' else url_for('dashboard.index')
    return render_template(
        '_error.html', tone='bad', glyph='x', code=code,
        title='Something seized up.',
        message="Whatever you just tried cramped up on our end. Your data's "
                "safe — nothing was committed. Catch your breath and try again.",
        diag=diag, quicklinks=False, show_retry=True,
        retry_label='Try again', retry_href=retry_href,
        mailto_href=_error_mailto(code, diag),
    ), 500


# Rate limiting. Defaults are intentionally absent — only the auth blueprint
# routes opt in (see routes/auth.py). Storage is in-process memory; across
# multiple workers each enforces independently, which is fine for the
# single-instance deploys this app targets. Swap in Redis (RATELIMIT_STORAGE_URI)
# if scaling up.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
    default_limits=[],
    headers_enabled=True,
)


def _workout_steps(description):
    """Split a workout description into discrete steps for bullet rendering."""
    if not description:
        return []
    if '\n' in description:
        parts = description.split('\n')
    else:
        parts = _re.split(r'\.\s+', description)
    steps = []
    for p in parts:
        p = p.strip().rstrip('.')
        p = _re.sub(r'^[\s\-•·–—]+', '', p)   # strip leading bullets/dashes
        p = _re.sub(r'^\d+[.)]\s*', '', p)      # strip leading numbers (1. or 1))
        p = p.strip()
        if p:
            steps.append(p)
    return steps


app.jinja_env.filters['workout_steps'] = _workout_steps

from routes.dashboard import bp as dashboard_bp
from routes.training import bp as training_bp
from routes.cardio import bp as cardio_bp
from routes.rx import bp as rx_bp
from routes.body import bp as body_bp
from routes.conditions import bp as conditions_bp
from routes.injuries import bp as injuries_bp
from routes.references import bp as references_bp
from routes.locales import bp as locales_bp
from routes.garmin import bp as garmin_bp
from routes.connections import bp as connections_bp
from routes.plans import bp as plans_bp
from routes.coaching import bp as coaching_bp
from routes.natural_log import bp as natural_log_bp
from routes.log import bp as log_bp
from routes.profile import bp as profile_bp
from routes.race_events import bp as race_events_bp
from routes.onboarding import bp as onboarding_bp
from routes.purchases import bp as purchases_bp
from routes.wellness import bp as wellness_bp
from routes.admin import bp as admin_bp
from routes.auth import bp as auth_bp, current_user, verify_bearer_token
from routes.oauth_callbacks import bp as oauth_callbacks_bp
from routes.status import bp as status_bp
from routes.coros import bp as coros_bp
from routes.polar import bp as polar_bp
from routes.ride_with_gps import bp as ride_with_gps_bp
from routes.strava import bp as strava_bp
from routes.whoop import bp as whoop_bp
from routes.trainingpeaks import bp as trainingpeaks_bp
from routes.zwift import bp as zwift_bp
from routes.nudges import bp as nudges_bp, get_active_nudges
from routes.ad_hoc_workouts import bp as ad_hoc_workouts_bp
from routes.plan_create import bp as plan_create_bp
from routes.plan_refresh import bp as plan_refresh_bp
from routes.logs import bp as logs_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(training_bp)
app.register_blueprint(cardio_bp)
app.register_blueprint(rx_bp)
app.register_blueprint(body_bp)
app.register_blueprint(conditions_bp)
app.register_blueprint(injuries_bp)
app.register_blueprint(references_bp)
app.register_blueprint(locales_bp)
app.register_blueprint(garmin_bp)
app.register_blueprint(connections_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(coaching_bp)
app.register_blueprint(natural_log_bp)
app.register_blueprint(log_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(race_events_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(wellness_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(oauth_callbacks_bp)
app.register_blueprint(status_bp)
app.register_blueprint(coros_bp)
app.register_blueprint(polar_bp)
app.register_blueprint(ride_with_gps_bp)
app.register_blueprint(strava_bp)
app.register_blueprint(whoop_bp)
app.register_blueprint(trainingpeaks_bp)
app.register_blueprint(zwift_bp)
app.register_blueprint(nudges_bp)
app.register_blueprint(ad_hoc_workouts_bp)
app.register_blueprint(plan_create_bp)
app.register_blueprint(plan_refresh_bp)
app.register_blueprint(logs_bp)
# COROS pushes workout-summary data to /coros/webhook from their servers,
# not from a browser session, so the global CSRF protection doesn't apply
# (and would 400 every push). Auth is via the `client` + `secret` request
# headers, verified inside the blueprint in Phase 6.
csrf.exempt(coros_bp)
# Polar pushes notifications to /polar/webhook from their AccessLink
# servers. Auth is via the Polar-Webhook-Signature HMAC-SHA256 header
# verified against POLAR_WEBHOOK_SECRET inside the blueprint (PR3).
csrf.exempt(polar_bp)
# Same rationale for Ride With GPS: pushes originate from RWGPS servers
# with an `x-rwgps-signature` HMAC header, not from a browser. Signature
# verification happens inside the blueprint when the stub is promoted.
csrf.exempt(ride_with_gps_bp)
# Strava / Whoop / TrainingPeaks / Zwift webhooks all originate from
# provider servers, not a browser session — same CSRF rationale.
csrf.exempt(strava_bp)
csrf.exempt(whoop_bp)
csrf.exempt(trainingpeaks_bp)
csrf.exempt(zwift_bp)
# Vercel POSTs log batches to /admin/logs/drain from its log-drain servers,
# not a browser session — same CSRF rationale as the provider webhooks. Auth
# is the x-vercel-signature HMAC-SHA1 verified against LOG_DRAIN_SECRET inside
# the blueprint (issue #350).
csrf.exempt(logs_bp)


# ── Auth gate ────────────────────────────────────────────────────────────────
# Endpoints that don't require a logged-in user. Anything else redirects to
# /auth/login when the user has no session. Per-user query scoping ships in
# Session 2 of the multi-user retrofit.
_AUTH_EXEMPT_ENDPOINTS = {
    'static',
    'auth.login',
    'auth.logout',
    'auth.register',
    'auth.forgot',
    'auth.reset',
    # Single endpoint covers every registered provider (slug allowlist
    # lives in routes/oauth_callbacks.py). Adding a new provider does
    # not require a change here.
    'oauth_callbacks.callback',
    # Health-check probe and COROS webhook stub: both are called by
    # external systems (uptime monitors, COROS push service) with no
    # session cookie.
    'status.status',
    'coros.webhook',
    'polar.webhook',
    'ride_with_gps.webhook',
    'strava.webhook',
    'whoop.webhook',
    'trainingpeaks.webhook',
    'zwift.webhook',
    # Vercel Cron hits these scanners with no session cookie; auth is via
    # the `Authorization: Bearer $CRON_SECRET` header verified inside the
    # route (`routes.auth.cron_authorized`).
    'nudges.scan_connect_provider_14d',
    'plan_create.cron_generate_pending',
    # Plan-gen diag endpoint: deliberately readable WITHOUT the app login so
    # an operator/agent debugging from outside a browser session can fetch the
    # real fault. Auth is verified INSIDE the route (`admin._diag_authorized`:
    # admin session OR constant-time DIAG_TOKEN match; no bypass when the token
    # is unset). Same in-route-auth pattern as the cron/webhook endpoints above
    # — it must be exempt from this global session wall or the wall shadows the
    # token check and the endpoint is unreachable except by a logged-in admin.
    'admin.plan_diag',
    # Vercel Log Drain sink + its token-authed reader (issue #350). The drain
    # ingest is verified by the x-vercel-signature HMAC; the query endpoint by
    # the same DIAG_TOKEN gate as plan_diag. Both must bypass the session wall:
    # Vercel carries no cookie, and an agent reads via token, not a browser.
    'logs.drain_ingest',
    'logs.query_logs',
}


@app.before_request
def _require_login():
    endpoint = request.endpoint or ''
    if endpoint in _AUTH_EXEMPT_ENDPOINTS:
        return None
    # Static files served from blueprints also include the dot-form 'X.static'.
    if endpoint.endswith('.static') or request.path.startswith('/static/'):
        return None

    # Bearer-token auth (headless API clients) is checked before the session
    # path so an external script's Authorization header beats any stale
    # session cookie that might be lying around. On a successful match we
    # stash the user id on g so current_user_id() picks it up, hydrate the
    # row the same way the session path does, and short-circuit the rest
    # of the gate.
    try:
        token_uid = verify_bearer_token(get_db())
    except Exception as e:
        print(f'auth: bearer-token verify failed: {e}')
        token_uid = None
    if token_uid:
        try:
            g.api_user_id = token_uid
            user = current_user(get_db())
        except Exception as e:
            print(f'auth: hydration failed for token user_id={token_uid}: {e}')
            user = None
        if user:
            g.current_user_row = user
            g.api_authed = True
            return None
        # Token resolved to a user that no longer exists — treat as unauthed.
        g.api_user_id = None

    uid = session.get('user_id')
    if uid:
        # Hydrate the user row once per request. Stash on `g` so the
        # context processor and any handler that wants the row can read
        # it without re-querying. This also defends against stale session
        # cookies pointing at a row that no longer exists — e.g. after a
        # DB swap (SQLite→Neon cutover) or an admin deletion. Without
        # this, the gate would happily admit a "ghost" user whose
        # templates render with `current_user=None`, hiding the nav
        # dropdown (and the only logout button) until they manually
        # navigate to /auth/logout.
        try:
            user = current_user(get_db())
        except Exception as e:
            # Surface any unexpected DB / decode failure in the logs
            # rather than silently rendering as a logged-out user.
            print(f'auth: hydration failed for user_id={uid}: {e}')
            user = None
        if user:
            g.current_user_row = user
            return None
        # Stale or unhydratable session — clear and re-prompt.
        session.clear()

    if request.method == 'GET':
        return redirect(url_for('auth.login', next=request.path))
    return ('Authentication required.', 401)


@app.context_processor
def _inject_current_user():
    """Expose the logged-in user to all templates as `current_user`.
    Reads the row hydrated by `_require_login` — single query per request."""
    return {'current_user': getattr(g, 'current_user_row', None)}


@app.context_processor
def _inject_active_nudges():
    """Expose undismissed `account_nudges` rows for the current user as
    `active_nudges` (v5 §A.2.4). Empty list when logged out or on
    SQLite dev. Reads via `routes.nudges.get_active_nudges` on every
    request, but the underlying query is one SELECT scoped by user_id
    + a partial-index-friendly WHERE — negligible per-render cost.
    """
    user = getattr(g, 'current_user_row', None)
    if not user:
        return {'active_nudges': []}
    try:
        return {'active_nudges': get_active_nudges(get_db(), user['id'])}
    except Exception as e:
        print(f'nudges: get_active_nudges failed: {e}')
        return {'active_nudges': []}


# Content-Security-Policy. Both script-src and style-src use per-request
# nonces and drop 'unsafe-inline'. Inline <script> blocks render
# nonce="{{ csp_nonce() }}"; inline event handler attributes have been
# refactored to data-attr delegation in static/app.js. Parser-set
# style="..." attributes have been refactored to utility classes (see
# static/style.css `.u-*` and Bootstrap utilities); dynamic widths use
# data-progress + a JS init pass in static/app.js. The one remaining
# <style> block (plans/view.html) renders the same nonce.
# Script-driven `element.style.foo = bar` is not filtered by CSP, so the
# JS-toggled `classList.toggle('d-none', …)` pattern is fine.
#
# What the lockdown buys:
#   connect-src 'self'     stops injected JS from POSTing exfil to externals
#   img-src 'self' data:   blocks pixel-tracker exfiltration
#   form-action 'self'     defends against form-action injection
#   frame-ancestors 'none' blocks clickjacking
#   base-uri 'self'        prevents <base href> injection
#   object-src 'none'      kills <object>/<embed>/Flash
#   nonce'd script-src     blocks XSS-injected inline <script>
#   nonce'd style-src      blocks XSS-injected inline style attrs / blocks
_CSP_BASE_DIRECTIVES = [
    "default-src 'self'",
    # script-src 'self' is fine for our /static/app.js. Nonce covers all
    # inline <script> blocks we render from templates. 'strict-dynamic'
    # would let nonce'd scripts load further scripts, but we don't need
    # that today — the third-party CDN imports are explicit <script src=...>
    # tags that match script-src 'self' https://cdn.jsdelivr.net.
    None,  # placeholder for script-src — filled per-request with the nonce
    None,  # placeholder for style-src  — filled per-request with the nonce
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
]
if os.environ.get('DATABASE_URL'):
    _CSP_BASE_DIRECTIVES.append('upgrade-insecure-requests')
_CSP_HEADER_NAME = (
    'Content-Security-Policy-Report-Only'
    if _envbool('CSP_REPORT_ONLY', default=False)
    else 'Content-Security-Policy'
)


def _csp_for_nonce(nonce: str) -> str:
    parts = list(_CSP_BASE_DIRECTIVES)
    parts[1] = (
        f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net"
    )
    parts[2] = (
        f"style-src 'self' 'nonce-{nonce}' "
        f"https://cdn.jsdelivr.net https://fonts.googleapis.com"
    )
    return '; '.join(parts)


@app.before_request
def _generate_csp_nonce():
    # 16 random bytes → 22 base64url chars. Per-request, so each response's
    # CSP header carries a fresh value that an attacker can't predict.
    g.csp_nonce = _secrets.token_urlsafe(16)


@app.context_processor
def _inject_csp_nonce():
    """Expose csp_nonce() to templates so every inline <script> can render
    nonce="{{ csp_nonce() }}". Falls back to '' if the before_request
    hook hasn't run (test client without an active request, etc.)."""
    return {'csp_nonce': lambda: getattr(g, 'csp_nonce', '')}


@app.after_request
def _set_security_headers(resp):
    # Defensive headers that don't depend on per-page tuning.
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault(
        'Permissions-Policy',
        'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
    )
    resp.headers.setdefault(
        _CSP_HEADER_NAME, _csp_for_nonce(getattr(g, 'csp_nonce', ''))
    )
    return resp

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
