"""Authentication: login, logout, registration, first-user bootstrap.

Session 1 of the multi-user retrofit. Domain queries are still unscoped —
this layer only gates entry. Per-user scoping lands in Session 2.

Registration is closed by default; set the env var `ALLOW_REGISTRATION=1`
to open it. The exception is the first-user bootstrap: when no users
exist in the DB, the next request lands on the register page regardless.
"""
import os
from datetime import datetime

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from database import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


def _registration_open() -> bool:
    return os.environ.get('ALLOW_REGISTRATION', '').strip() in ('1', 'true', 'yes', 'on')


def _no_users(db) -> bool:
    row = db.execute('SELECT COUNT(*) AS n FROM users').fetchone()
    return (row['n'] if row else 0) == 0


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _check_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def current_user_id():
    """Flask session user id, or None when nobody is logged in."""
    return session.get('user_id')


def current_user(db):
    """Hydrate the logged-in user row, or None."""
    uid = current_user_id()
    if not uid:
        return None
    row = db.execute(
        'SELECT id, username, email, display_name FROM users WHERE id=?', (uid,)
    ).fetchone()
    return dict(row) if row else None


@bp.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db()
    if _no_users(db):
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('auth/login.html', username=username)

        row = db.execute(
            'SELECT id, password_hash FROM users WHERE username=?', (username,)
        ).fetchone()
        if not row or not _check_password(password, row['password_hash']):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html', username=username)

        session.clear()
        session['user_id'] = row['id']
        session['username'] = username
        db.execute('UPDATE users SET last_login=? WHERE id=?',
                   (datetime.utcnow().isoformat(timespec='seconds'), row['id']))
        db.commit()

        next_url = request.args.get('next') or url_for('dashboard.index')
        # Reject off-site redirects for safety.
        if not next_url.startswith('/'):
            next_url = url_for('dashboard.index')
        return redirect(next_url)

    return render_template('auth/login.html', username='')


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('Signed out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db()
    is_bootstrap = _no_users(db)
    if not is_bootstrap and not _registration_open():
        return ('Registration is closed.', 403)

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip() or None
        display_name = (request.form.get('display_name') or '').strip() or None
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''

        errors = []
        if len(username) < 3 or len(username) > 32:
            errors.append('Username must be 3–32 characters.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if username and db.execute(
            'SELECT 1 FROM users WHERE username=?', (username,)
        ).fetchone():
            errors.append('Username already taken.')
        if email and db.execute(
            'SELECT 1 FROM users WHERE email=?', (email,)
        ).fetchone():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html',
                                   username=username, email=email or '',
                                   display_name=display_name or '',
                                   is_bootstrap=is_bootstrap)

        cur = db.execute(
            'INSERT INTO users (username, email, password_hash, display_name) '
            'VALUES (?,?,?,?)',
            (username, email, _hash_password(password), display_name)
        )
        db.commit()

        session.clear()
        session['user_id'] = cur.lastrowid
        session['username'] = username
        flash(f'Account created — welcome, {display_name or username}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html',
                           username='', email='', display_name='',
                           is_bootstrap=is_bootstrap)
