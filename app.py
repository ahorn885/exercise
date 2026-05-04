import os
import re as _re
from flask import Flask, request, redirect, url_for, session, g
from database import init_app, get_db

app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE'] = os.path.join(app.instance_path, 'training.db')
app.secret_key = os.environ.get('SECRET_KEY', 'ar-training-2026')

if os.environ.get('DATABASE_URL'):
    # Postgres (production) — auto-migrate schema on every cold start
    # All statements use IF NOT EXISTS so this is safe to run repeatedly.
    from init_db import init_postgres
    try:
        init_postgres()
    except Exception as _e:
        print(f'Warning: DB init skipped: {_e}')
else:
    # SQLite (local dev)
    os.makedirs(app.instance_path, exist_ok=True)
    from init_db import init_sqlite
    init_sqlite()

init_app(app)


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
from routes.auth import bp as auth_bp, current_user

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
}


@app.before_request
def _require_login():
    endpoint = request.endpoint or ''
    if endpoint in _AUTH_EXEMPT_ENDPOINTS:
        return None
    if session.get('user_id'):
        return None
    # Static files served from blueprints also include the dot-form 'X.static'.
    if endpoint.endswith('.static'):
        return None
    if request.path.startswith('/static/'):
        return None
    if request.method == 'GET':
        return redirect(url_for('auth.login', next=request.path))
    return ('Authentication required.', 401)


@app.context_processor
def _inject_current_user():
    """Expose the logged-in user to all templates as `current_user`."""
    if not session.get('user_id'):
        return {'current_user': None}
    try:
        return {'current_user': current_user(get_db())}
    except Exception:
        return {'current_user': None}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
