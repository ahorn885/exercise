"""Admin dashboard.

Gated to user_id == 1 (the bootstrap user, conventionally the operator).
Adding more admin views: build them inside this blueprint and keep the
same `_require_admin()` gate at the top of every handler.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request

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
    db.execute('DELETE FROM wellness_self_report          WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_auth                   WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM garmin_workouts               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM locale_equipment              WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM locale_profiles               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM clothing_options              WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM current_rx                    WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM athlete_profile               WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM user_purchase_recommendations WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM api_tokens                    WHERE user_id = ?', (user_id,))
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
        # Audit the action in the same transaction as the delete — either
        # both succeed or both roll back. actor_user_id captured before the
        # commit so the FK reference is still valid.
        db.execute(
            'INSERT INTO admin_audit '
            '(actor_user_id, action, target_user_id, target_username) '
            'VALUES (?,?,?,?)',
            (current_user_id(), 'delete_user', user_id, username)
        )
        db.commit()
    except Exception as e:
        flash(f'Delete failed: {e}', 'danger')
        return redirect(url_for('admin.dashboard'))

    flash(f'Deleted user "{username}" and all associated data.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/audit')
def audit():
    """Read view over the admin_audit log.

    Filterable by action and actor via query string. Cap rows returned —
    the table only grows on admin mutations, so the cap is generous, but
    we'd rather page than render unbounded.
    """
    _require_admin()
    db = get_db()

    action = (request.args.get('action') or '').strip()
    actor = (request.args.get('actor') or '').strip()
    limit = 500

    where = []
    params: list = []
    if action:
        where.append('a.action = ?')
        params.append(action)
    if actor:
        # Accept either a numeric id or a username substring.
        if actor.isdigit():
            where.append('a.actor_user_id = ?')
            params.append(int(actor))
        else:
            where.append('u.username LIKE ?')
            params.append(f'%{actor}%')
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    rows = db.execute(
        f'''SELECT a.id, a.actor_user_id, u.username AS actor_username,
                   a.action, a.target_user_id, a.target_username,
                   a.details, a.created_at
              FROM admin_audit a
              LEFT JOIN users u ON u.id = a.actor_user_id
              {where_sql}
             ORDER BY a.id DESC
             LIMIT {limit}''',
        params,
    ).fetchall()

    # Distinct action values for the filter dropdown.
    actions = [
        r['action'] for r in db.execute(
            'SELECT DISTINCT action FROM admin_audit ORDER BY action'
        ).fetchall()
    ]

    return render_template(
        'admin/audit.html',
        rows=rows, actions=actions,
        selected_action=action, selected_actor=actor,
        limit=limit,
    )
