import os
from flask import Flask
from database import init_app

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
