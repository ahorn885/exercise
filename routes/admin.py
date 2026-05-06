"""Admin dashboard.

Gated to user_id == 1 (the bootstrap user, conventionally the operator).
Only surface today is the user list + cascade-delete for cleanup of test
accounts. Adding more admin views: build them inside this blueprint and
keep the same `_require_admin()` gate at the top of every handler.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, abort

from database import get_db
from routes.auth import current_user_id

bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_USER_ID = 1


def _require_admin():
    if current_user_id() != ADMIN_USER_ID:
        abort(403)


# Order matters: child rows must be deleted before their parents so the
# FK constraints don't reject the delete. Mirrors the SQL block we ran
# manually for the first test-user cleanup. Each tuple is (sql, params)
# so we can keep one with a sub-SELECT for the parent-JOIN scoped tables.
def _delete_user_and_data(db, user_id):
    db.execute('DELETE FROM training_log_sets             WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_item_disposition         WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_items                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM plan_reviews WHERE plan_id IN '
               '(SELECT id FROM training_plans WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM plan_travel  WHERE plan_id IN '
               '(SELECT id FROM training_plans WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM coaching_chat                 WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_plans                WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM training_sessions             WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM cardio_log                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM body_metrics                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM conditions_log                WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM injury_exercise_modifications WHERE injury_id IN '
               '(SELECT id FROM injury_log WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM injury_log                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM coaching_preferences          WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM feedback_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM wellness_log                  WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_auth                   WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_workouts               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM locale_equipment              WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM locale_profiles               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM clothing_options              WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM current_rx                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM athlete_profile               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM user_purchase_recommendations WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM users                         WHERE id = ?',      (user_id,))


@bp.route('/')
def dashboard():
    _require_admin()
    db = get_db()
    users = db.execute(
        '''SELECT u.id, u.username, u.email, u.display_name,
                  u.created_at, u.last_login,
                  (SELECT COUNT(*) FROM training_log    WHERE user_id = u.id) AS strength_logs,
                  (SELECT COUNT(*) FROM cardio_log      WHERE user_id = u.id) AS cardio_logs,
                  (SELECT COUNT(*) FROM training_plans  WHERE user_id = u.id) AS plans
             FROM users u
            ORDER BY u.id'''
    ).fetchall()
    return render_template('admin/dashboard.html', users=users,
                           admin_user_id=ADMIN_USER_ID)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    _require_admin()
    if user_id == ADMIN_USER_ID:
        flash("Refusing to delete the admin user.", 'danger')
        return redirect(url_for('admin.dashboard'))

    db = get_db()
    row = db.execute(
        'SELECT id, username FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    if not row:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    username = row['username']
    try:
        _delete_user_and_data(db, user_id)
        db.commit()
    except Exception as e:
        flash(f'Delete failed: {e}', 'danger')
        return redirect(url_for('admin.dashboard'))

    flash(f'Deleted user "{username}" and all associated data.', 'success')
    return redirect(url_for('admin.dashboard'))
