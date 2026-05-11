"""Authentication: login, logout, registration, first-user bootstrap,
password reset.

Session 1 of the multi-user retrofit. Domain queries are still unscoped —
this layer only gates entry. Per-user scoping lands in Session 2.

Registration is open by default. To close it again (e.g. after a smoke
test), set `ALLOW_REGISTRATION=0` (or `false`/`no`/`off`). The first-user
bootstrap path is unconditional: when no users exist in the DB, the next
request lands on the register page regardless.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from zxcvbn import zxcvbn

from database import get_db
from email_helper import send_email, email_configured

PASSWORD_RESET_TTL_MIN = 30
# zxcvbn score table: 0=too guessable, 1=very guessable,
# 2=somewhat guessable, 3=safely unguessable, 4=very unguessable.
# 3 protects against offline slow-hash attack; with bcrypt + the rate
# limit on /auth/login, this is a comfortable bar for the friends-only
# install. Crank to 4 if onboarding strangers later.
MIN_PASSWORD_SCORE = 3
MIN_PASSWORD_LENGTH = 8

bp = Blueprint('auth', __name__, url_prefix='/auth')


def _registration_open() -> bool:
    return os.environ.get('ALLOW_REGISTRATION', '').strip().lower() not in ('0', 'false', 'no', 'off')


def _no_users(db) -> bool:
    row = db.execute('SELECT COUNT(*) AS n FROM users').fetchone()
    return (row['n'] if row else 0) == 0


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _password_strength_errors(password: str, *, user_inputs=None) -> list[str]:
    """Return a list of error messages if `password` is too weak; empty list otherwise.

    `user_inputs` is fed to zxcvbn so it knows to penalize passwords that
    incorporate the username, email, or display name. zxcvbn handles
    breach lists, keyboard patterns, dates, l33t-substitutions, and dict
    matches in 30+ languages — all of which a hand-rolled rule set
    misses.
    """
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.')
        # No point running zxcvbn on a too-short string — it'll obviously fail.
        return errors
    result = zxcvbn(password, user_inputs=[s for s in (user_inputs or []) if s])
    if result['score'] < MIN_PASSWORD_SCORE:
        feedback = result.get('feedback') or {}
        warning = (feedback.get('warning') or '').strip()
        suggestions = [s.strip() for s in (feedback.get('suggestions') or []) if s and s.strip()]
        msg = 'Password is too weak.'
        if warning:
            msg += f' {warning}.'
        if suggestions:
            msg += ' ' + ' '.join(suggestions)
        errors.append(msg)
    return errors


def _check_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def current_user_id():
    """Authenticated user id for this request, or None when unauthed.

    Reads from `g.api_user_id` first (set by the auth gate when a
    valid Bearer token authed the request) so token-authed callers
    see the same per-user scoping as session-authed ones. Falls back
    to the Flask session.
    """
    api_uid = getattr(g, 'api_user_id', None)
    if api_uid:
        return api_uid
    return session.get('user_id')


# ── API tokens ──────────────────────────────────────────────────────────────
# Per-user bearer tokens for headless access to /coaching/api/*. Plaintext is
# shown to the user once on creation and never persisted; we store SHA-256.
# SHA-256 (not bcrypt) is fine because tokens are 32 bytes of cryptographic
# random — there's nothing to brute-force.

API_TOKEN_PREFIX = 'aid_'


def _hash_api_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


def generate_api_token() -> tuple[str, str]:
    """Return (plaintext, hash). Plaintext is shown to the user once."""
    raw = secrets.token_urlsafe(32)
    plaintext = f'{API_TOKEN_PREFIX}{raw}'
    return plaintext, _hash_api_token(plaintext)


def verify_bearer_token(db) -> int | None:
    """Resolve an `Authorization: Bearer <token>` header to a user id.

    Returns None on missing/malformed/revoked/expired/unknown tokens.
    Updates `last_used_at` on a hit so the operator can see which tokens
    are actually in use.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.lower().startswith('bearer '):
        return None
    plaintext = auth[7:].strip()
    if not plaintext.startswith(API_TOKEN_PREFIX):
        return None
    h = _hash_api_token(plaintext)
    row = db.execute(
        'SELECT id, user_id, revoked_at, expires_at FROM api_tokens '
        'WHERE token_hash = ?',
        (h,)
    ).fetchone()
    if not row or row['revoked_at']:
        return None
    if row['expires_at'] and _is_past(row['expires_at']):
        return None
    db.execute(
        'UPDATE api_tokens SET last_used_at = ? WHERE id = ?',
        (datetime.utcnow().isoformat(timespec='seconds'), row['id'])
    )
    db.commit()
    return row['user_id']


def _is_past(ts) -> bool:
    """Return True if the timestamp (datetime from Postgres, ISO-8601 string
    from SQLite) is at or before now. Defensive parse — on any failure
    treat as not-expired so a malformed value doesn't lock a user out."""
    if ts is None:
        return False
    if isinstance(ts, datetime):
        cmp = ts.replace(tzinfo=None) if ts.tzinfo else ts
        return cmp <= datetime.utcnow()
    try:
        s = str(ts).strip()
        # Strip trailing 'Z' or timezone offset for naive comparison.
        if s.endswith('Z'):
            s = s[:-1]
        parsed = datetime.fromisoformat(s.split('+')[0].split(' UTC')[0])
        return parsed <= datetime.utcnow()
    except Exception:
        return False


def current_user(db):
    """Hydrate the logged-in user row, or None."""
    uid = current_user_id()
    if not uid:
        return None
    row = db.execute(
        'SELECT id, username, email, display_name FROM users WHERE id=?', (uid,)
    ).fetchone()
    return dict(row) if row else None


def _limit(spec):
    """Apply a Flask-Limiter rate limit to the wrapped POST handler.

    Imports lazily to avoid a circular import (app.py imports this module).
    Returns the decorator without limit when limiter isn't initialized yet
    (e.g. during unit-test imports that build the blueprint without an app).
    """
    def decorator(fn):
        try:
            from app import limiter
        except Exception:
            return fn
        return limiter.limit(spec, methods=['POST'])(fn)
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
@_limit('10 per 5 minutes')
def login():
    db = get_db()
    if _no_users(db):
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('auth/login.html', username=username,
                                   registration_open=_registration_open())

        row = db.execute(
            'SELECT id, password_hash FROM users WHERE username=?', (username,)
        ).fetchone()
        if not row or not _check_password(password, row['password_hash']):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html', username=username,
                                   registration_open=_registration_open())

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

    return render_template('auth/login.html', username='',
                           registration_open=_registration_open())


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('Signed out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
@_limit('10 per hour')
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
        errors.extend(_password_strength_errors(
            password,
            user_inputs=[username, email or '', display_name or '']
        ))
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
            'VALUES (?,?,?,?) RETURNING id',
            (username, email, _hash_password(password), display_name)
        )
        new_user_id = cur.lastrowid
        # Seed the new user's current_rx so /rx isn't blank on their first
        # session. Idempotent via composite UNIQUE(user_id, exercise) —
        # safe to re-run from the next cold-start init pass too.
        try:
            from init_db import _seed_current_rx_for_user
            is_pg = bool(os.environ.get('DATABASE_URL'))
            _seed_current_rx_for_user(db, new_user_id, is_postgres=is_pg)
        except Exception:
            # Don't block registration on a seed failure — init will retry.
            pass
        db.commit()

        session.clear()
        session['user_id'] = new_user_id
        session['username'] = username
        flash(f'Account created — welcome, {display_name or username}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html',
                           username='', email='', display_name='',
                           is_bootstrap=is_bootstrap)


# ── Password reset ───────────────────────────────────────────────────────────

@bp.route('/forgot', methods=['GET', 'POST'])
@_limit('5 per 15 minutes')
def forgot():
    """Request a password-reset email.

    Always renders the same "if an account exists, an email is on its way"
    response on POST so this endpoint can't be used to enumerate
    registered email addresses. Real users see the link land in their
    inbox; non-users see the same success message and nothing happens.
    """
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if email:
            db = get_db()
            row = db.execute(
                'SELECT id, username, display_name FROM users WHERE LOWER(email) = ?',
                (email,)
            ).fetchone()
            if row:
                token = secrets.token_urlsafe(32)
                now = datetime.utcnow()
                expires = now + timedelta(minutes=PASSWORD_RESET_TTL_MIN)
                db.execute(
                    'INSERT INTO password_resets (token, user_id, expires_at) VALUES (?,?,?)',
                    (token, row['id'], expires.isoformat(timespec='seconds'))
                )
                db.commit()
                reset_url = url_for('auth.reset', token=token, _external=True)
                _send_password_reset_email(email, row['display_name'] or row['username'],
                                            reset_url)
        flash('If an account exists for that email, a reset link is on its way. '
              'Check your inbox (and spam folder). Links expire in '
              f'{PASSWORD_RESET_TTL_MIN} minutes.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot.html',
                           email_configured=email_configured())


@bp.route('/reset/<token>', methods=['GET', 'POST'])
@_limit('10 per 15 minutes')
def reset(token):
    """Complete a password reset with a single-use, time-limited token."""
    db = get_db()
    row = db.execute(
        'SELECT pr.token, pr.user_id, pr.expires_at, pr.used_at, '
        '       u.username, u.display_name '
        '  FROM password_resets pr '
        '  JOIN users u ON u.id = pr.user_id '
        ' WHERE pr.token = ?',
        (token,)
    ).fetchone()
    if not row or row['used_at']:
        return render_template('auth/reset.html', token=None,
                               error='This reset link is invalid or has already been used.')
    expires_at = row['expires_at']
    expires_dt = (expires_at if isinstance(expires_at, datetime)
                  else datetime.fromisoformat(str(expires_at)))
    if expires_dt < datetime.utcnow():
        return render_template('auth/reset.html', token=None,
                               error=f'This reset link has expired. Request a new one from /auth/forgot.')

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        # Username from the row above seeds zxcvbn so a password matching
        # the user's name is rejected even though we don't take it as input.
        strength_errors = _password_strength_errors(
            password, user_inputs=[row['username'], row['display_name'] or '']
        )
        if strength_errors:
            for e in strength_errors:
                flash(e, 'danger')
            return render_template('auth/reset.html', token=token, error=None)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset.html', token=token, error=None)

        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (_hash_password(password), row['user_id']))
        db.execute('UPDATE password_resets SET used_at = ? WHERE token = ?',
                   (datetime.utcnow().isoformat(timespec='seconds'), token))
        db.commit()
        # Clear any active session — the user can sign back in with the new
        # password. Defends against an attacker who hijacked a session via
        # a leaked cookie still being authenticated after the reset.
        session.clear()
        flash('Password updated. Sign in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset.html', token=token, error=None,
                           username=row['username'])


def _send_password_reset_email(to_address: str, display_name: str, reset_url: str) -> None:
    subject = 'AIDSTATION — password reset'
    text = (
        f'Hi {display_name},\n\n'
        f'Use this link to set a new AIDSTATION password:\n\n'
        f'  {reset_url}\n\n'
        f'The link expires in {PASSWORD_RESET_TTL_MIN} minutes and can only '
        f'be used once. If you didn\'t request a reset, you can ignore this '
        f'email — your account is unchanged.\n\n'
        f'— AIDSTATION\n'
    )
    html = f"""<!doctype html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#0E0F11;">
<p>Hi {display_name},</p>
<p>Use this link to set a new AIDSTATION password:</p>
<p><a href="{reset_url}" style="display:inline-block;padding:10px 18px;background:#ED7A2D;color:#fff;text-decoration:none;border-radius:4px;">Set a new password</a></p>
<p style="font-size:12px;color:#666;">Or paste this into your browser:<br><span style="font-family:ui-monospace,monospace;word-break:break-all;">{reset_url}</span></p>
<p style="font-size:12px;color:#666;">The link expires in {PASSWORD_RESET_TTL_MIN} minutes and can only be used once. If you didn't request a reset, you can ignore this email — your account is unchanged.</p>
<p style="font-size:12px;color:#666;">— AIDSTATION</p>
</body></html>"""
    send_email(to_address, subject, text, html)
