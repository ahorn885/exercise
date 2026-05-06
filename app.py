import os
import re as _re
from flask import Flask, request, redirect, url_for, session, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import init_app, get_db, sqlite_path

app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE'] = sqlite_path()

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

if os.environ.get('DATABASE_URL'):
    # Postgres (production) — auto-migrate schema on every cold start
    # All statements use IF NOT EXISTS so this is safe to run repeatedly.
    from init_db import init_postgres
    try:
        init_postgres()
    except Exception as _e:
        print(f'Warning: DB init skipped: {_e}')
else:
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    from init_db import init_sqlite
    try:
        init_sqlite()
    except Exception as _e:
        # Don't fail module import on init errors — surface them in logs so
        # the actual route 500 (not a cryptic import-time failure) is what
        # the operator sees.
        print(f'Warning: SQLite init failed: {_e}')

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
from routes.plans import bp as plans_bp
from routes.coaching import bp as coaching_bp
from routes.natural_log import bp as natural_log_bp
from routes.profile import bp as profile_bp
from routes.purchases import bp as purchases_bp
from routes.admin import bp as admin_bp
from routes.auth import bp as auth_bp, current_user, verify_bearer_token

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
app.register_blueprint(plans_bp)
app.register_blueprint(coaching_bp)
app.register_blueprint(natural_log_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)


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


# Content-Security-Policy. 'unsafe-inline' on script-src/style-src is a
# concession to the existing template inline-event-handler usage (onclick,
# onsubmit, onchange, inline <script> blocks, inline style="..."). Migrating
# to nonces would touch every template and is its own session — but even
# with 'unsafe-inline' allowed for scripts/styles, the directives below
# still close the data-exfiltration vectors that matter most: connect-src
# stops JS from POSTing to external origins, img-src stops pixel-tracker
# leaks, form-action keeps form submissions same-origin, frame-ancestors
# blocks clickjacking, object-src kills <object>/Flash, base-uri prevents
# <base href> injection. upgrade-insecure-requests only fires on HTTPS.
_CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
]
if os.environ.get('DATABASE_URL'):
    # Production is HTTPS-fronted — silently rewrite any stray http:// asset
    # references to https. Skipped on local dev (which is plain HTTP).
    _CSP_DIRECTIVES.append('upgrade-insecure-requests')
_CSP_HEADER_VALUE = '; '.join(_CSP_DIRECTIVES)
# Set CSP_REPORT_ONLY=1 to deploy as Content-Security-Policy-Report-Only —
# violations are logged by the browser console but not enforced. Useful
# for catching unexpected breakage before flipping to enforcement.
_CSP_HEADER_NAME = (
    'Content-Security-Policy-Report-Only'
    if _envbool('CSP_REPORT_ONLY', default=False)
    else 'Content-Security-Policy'
)


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
    resp.headers.setdefault(_CSP_HEADER_NAME, _CSP_HEADER_VALUE)
    return resp

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
