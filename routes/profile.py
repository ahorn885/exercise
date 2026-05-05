"""Profile blueprint (Session 4).

Single page at `/profile` with three sections:
  - Athlete profile — DOB, sex, height, target event, weekly hours, etc.
  - Coach memory — list of `coaching_preferences` rows for the current
    user, each with provenance (which feedback_log row produced it),
    delete buttons, and a manual-add form.
  - Account — username display + change-password form.

All writes are scoped to the current user. Coach memory rows from the
auto-capture pipeline (Session 0) are surfaced verbatim with their
`source` and `captured_at` from the originating `feedback_log` row.
"""

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from database import get_db
from routes.auth import current_user_id, _hash_password, _check_password
from athlete import (
    PROFILE_FIELDS, TRAINING_WINDOWS,
    get_athlete_profile, upsert_athlete_profile,
)


bp = Blueprint('profile', __name__, url_prefix='/profile')


# Categories shown in the manual-add coaching_preferences dropdown. Mirrors
# the categories the auto-extractor (coaching.py:_FEEDBACK_EXTRACT_PROMPT)
# emits, so manually-added prefs slot in alongside auto-captured ones.
PREFERENCE_CATEGORIES = (
    'avoid_exercise', 'prefer_exercise',
    'nutrition', 'training', 'scheduling', 'equipment', 'general',
)


def _load_memory(db, user_id):
    """Return the coach-memory rows for the current user with provenance.

    Each preference row joins LEFT to feedback_log via source_feedback_id
    so manually-added prefs (no source) render with empty provenance.
    """
    rows = db.execute(
        '''SELECT cp.id, cp.category, cp.content, cp.permanent, cp.created_at,
                  cp.source_feedback_id,
                  fl.source as fb_source, fl.captured_at as fb_captured_at,
                  fl.raw_content as fb_raw_content
           FROM coaching_preferences cp
           LEFT JOIN feedback_log fl ON fl.id = cp.source_feedback_id
           WHERE cp.user_id = ?
           ORDER BY cp.created_at DESC''',
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


@bp.route('/', methods=['GET', 'POST'])
def edit():
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        # Profile section — POST body carries the profile fields. Empty
        # strings are coerced to None so we don't store '' for unset.
        f = request.form

        def _str(key):
            v = (f.get(key) or '').strip()
            return v or None

        def _num(key, cast=float):
            v = (f.get(key) or '').strip()
            if not v:
                return None
            try:
                return cast(v)
            except (ValueError, TypeError):
                return None

        window = _str('training_window')
        if window not in (None,) + TRAINING_WINDOWS:
            window = None

        upsert_athlete_profile(
            db, uid,
            date_of_birth=_str('date_of_birth'),
            sex=_str('sex'),
            height_cm=_num('height_cm'),
            primary_sport=_str('primary_sport'),
            target_event_name=_str('target_event_name'),
            target_event_date=_str('target_event_date'),
            weekly_hours_target=_num('weekly_hours_target'),
            training_window=window,
            notes=_str('notes'),
        )
        db.commit()
        flash('Profile saved.', 'success')
        return redirect(url_for('profile.edit'))

    profile = get_athlete_profile(db, uid) or {}
    memory = _load_memory(db, uid)
    user_row = db.execute(
        'SELECT username, display_name, email, last_login FROM users WHERE id=?', (uid,)
    ).fetchone()
    return render_template(
        'profile/edit.html',
        profile=profile,
        memory=memory,
        preference_categories=PREFERENCE_CATEGORIES,
        training_windows=TRAINING_WINDOWS,
        user_row=dict(user_row) if user_row else {},
    )


@bp.route('/preference/add', methods=['POST'])
def add_preference():
    """Manually add a coaching preference. Provenance is left NULL —
    the UI label distinguishes manual entries from auto-captured ones."""
    db = get_db()
    uid = current_user_id()
    category = (request.form.get('category') or '').strip()
    content = (request.form.get('content') or '').strip()
    permanent = 1 if request.form.get('permanent') else 0

    if category not in PREFERENCE_CATEGORIES:
        flash('Unknown preference category.', 'danger')
        return redirect(url_for('profile.edit'))
    if not content:
        flash('Preference content required.', 'danger')
        return redirect(url_for('profile.edit'))

    db.execute(
        'INSERT INTO coaching_preferences (category, content, permanent, user_id) '
        'VALUES (?, ?, ?, ?)',
        (category, content, permanent, uid)
    )
    db.commit()
    flash('Preference added.', 'success')
    return redirect(url_for('profile.edit'))


@bp.route('/preference/<int:pref_id>/delete', methods=['POST'])
def delete_preference(pref_id):
    """Delete a coaching preference. Scoped on user_id — a crafted
    POST can't reach another user's row."""
    db = get_db()
    db.execute(
        'DELETE FROM coaching_preferences WHERE id=? AND user_id=?',
        (pref_id, current_user_id())
    )
    db.commit()
    flash('Preference removed.', 'info')
    return redirect(url_for('profile.edit'))


@bp.route('/feedback/<int:fb_id>')
def view_feedback(fb_id):
    """Show the original feedback_log row that produced a preference.
    Scoped on user_id; 404s for other users' rows."""
    db = get_db()
    row = db.execute(
        'SELECT id, source, raw_content, captured_at FROM feedback_log '
        'WHERE id=? AND user_id=?',
        (fb_id, current_user_id())
    ).fetchone()
    if not row:
        abort(404)
    return render_template('profile/feedback.html', feedback=dict(row))


@bp.route('/password', methods=['POST'])
def change_password():
    db = get_db()
    uid = current_user_id()
    current = request.form.get('current_password') or ''
    new = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''

    if not current or not new:
        flash('Current and new password are both required.', 'danger')
        return redirect(url_for('profile.edit'))
    if len(new) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('profile.edit'))
    if new != confirm:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('profile.edit'))

    row = db.execute('SELECT password_hash FROM users WHERE id=?', (uid,)).fetchone()
    if not row or not _check_password(current, row['password_hash']):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('profile.edit'))

    db.execute(
        'UPDATE users SET password_hash=? WHERE id=?',
        (_hash_password(new), uid)
    )
    db.commit()
    flash('Password changed.', 'success')
    return redirect(url_for('profile.edit'))
