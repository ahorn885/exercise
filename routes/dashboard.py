from flask import Blueprint, render_template
from database import get_db

bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    db = get_db()

    stats = {
        'training_total': db.execute('SELECT COUNT(*) FROM training_log').fetchone()[0],
        'cardio_total': db.execute('SELECT COUNT(*) FROM cardio_log').fetchone()[0],
        'active_injuries': db.execute("SELECT COUNT(*) FROM injury_log WHERE status='Active'").fetchone()[0],
        'exercises_progress': db.execute("SELECT COUNT(*) FROM current_rx WHERE last_outcome='PROGRESS \u2191'").fetchone()[0],
        'latest_weight': None,
    }

    wt = db.execute('SELECT weight_lbs, date FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
    if wt:
        stats['latest_weight'] = wt['weight_lbs']
        stats['weight_date'] = wt['date']

    recent_training = db.execute(
        'SELECT date, exercise, actual_sets, actual_reps, actual_weight, outcome FROM training_log ORDER BY date DESC, id DESC LIMIT 10'
    ).fetchall()

    recent_cardio = db.execute(
        'SELECT date, activity, duration_min, distance_mi, avg_hr FROM cardio_log ORDER BY date DESC LIMIT 5'
    ).fetchall()

    return render_template('dashboard.html', stats=stats,
                           recent_training=recent_training,
                           recent_cardio=recent_cardio)
