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
import hmac
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from zxcvbn import zxcvbn

import mfa
from database import get_db
from email_helper import send_email, email_configured
from email_templates import render_email, account_security_url, format_timestamp
from routes import provider_identity as pi
from sms_helper import send_sms, send_whatsapp

PASSWORD_RESET_TTL_MIN = 30
# Email-verification links live longer than reset links — there's no security
# urgency to a verify link (it only flips a flag; it can't change credentials),
# and athletes click them at leisure.
EMAIL_VERIFY_TTL_HOURS = 24
# Admin invite links (#274). A week is plenty for someone to accept; expired
# invites can be re-issued.
INVITE_TTL_DAYS = 7
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


def cron_authorized() -> bool:
    """True iff the request carries `Authorization: Bearer $CRON_SECRET`.

    Vercel Cron sends this header automatically once `CRON_SECRET` is set
    in the project env. Constant-time compare via `hmac.compare_digest`
    guards against timing side-channels. Returns False when `CRON_SECRET`
    isn't set so a misconfigured production deploy fails closed rather than
    running token-gated cron endpoints unauthenticated.
    """
    expected = os.environ.get('CRON_SECRET') or ''
    if not expected:
        return False
    header = request.headers.get('Authorization') or ''
    prefix = 'Bearer '
    if not header.startswith(prefix):
        return False
    return hmac.compare_digest(header[len(prefix):], expected)


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
                                   registration_open=_registration_open(),
                                   signin_providers=pi.enabled_signin_providers())

        row = db.execute(
            'SELECT id, password_hash FROM users WHERE username=?', (username,)
        ).fetchone()
        if not row or not _check_password(password, row['password_hash']):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html', username=username,
                                   registration_open=_registration_open(),
                                   signin_providers=pi.enabled_signin_providers())

        next_url = request.args.get('next') or url_for('dashboard.index')

        if mfa.is_enabled(db, row['id']):
            # Password is correct, but this account has 2FA on — do NOT grant a
            # session yet. Stash a short-lived pending marker that the
            # /auth/totp challenge converts into a real login once the
            # authenticator code checks out. `session.clear()` first so no
            # stale auth state lingers while the second factor is outstanding.
            session.clear()
            session['totp_pending_user_id'] = row['id']
            session['totp_pending_username'] = username
            session['totp_pending_next'] = (
                next_url if next_url.startswith('/') else url_for('dashboard.index')
            )
            return redirect(url_for('auth.totp_challenge'))

        return _finalize_login(db, row['id'], username, next_url)

    return render_template('auth/login.html', username='',
                           registration_open=_registration_open(),
                           signin_providers=pi.enabled_signin_providers())


def _finalize_login(db, user_id, username, next_url):
    """Grant a real session and bounce to `next_url`. Shared by the
    single-factor login path and the 2FA challenge so last_login bookkeeping
    and the open-redirect guard live in one place."""
    session.clear()
    session['user_id'] = user_id
    session['username'] = username
    db.execute('UPDATE users SET last_login=? WHERE id=?',
               (datetime.utcnow().isoformat(timespec='seconds'), user_id))
    db.commit()
    # Reject off-site redirects for safety.
    if not next_url or not next_url.startswith('/'):
        next_url = url_for('dashboard.index')
    return redirect(next_url)


@bp.route('/totp', methods=['GET', 'POST'])
@_limit('10 per 5 minutes')
def totp_challenge():
    """Second-factor gate for accounts with 2FA enabled (#265).

    Reachable only mid-login: `login()` sets `totp_pending_user_id` after a
    correct password but withholds the session until a valid TOTP lands here.
    No pending marker → nothing to challenge, so bounce to /auth/login. The
    endpoint is in `_AUTH_EXEMPT_ENDPOINTS` (the user isn't logged in yet) and
    rate-limited to blunt code brute-forcing."""
    pending_uid = session.get('totp_pending_user_id')
    if not pending_uid:
        return redirect(url_for('auth.login'))
    db = get_db()

    if request.method == 'POST':
        row = db.execute(
            'SELECT secret, confirmed_at FROM user_totp WHERE user_id = ?',
            (pending_uid,)
        ).fetchone()
        if not row or not row['confirmed_at']:
            # 2FA was turned off out from under this half-finished login (e.g. a
            # password reset in another tab cleared it). Drop the pending state
            # and send them back to a clean sign-in.
            _clear_totp_pending()
            flash('Two-factor authentication is no longer required. '
                  'Please sign in again.', 'info')
            return redirect(url_for('auth.login'))
        if mfa.verify_code(row['secret'], request.form.get('code') or ''):
            return _finalize_login(
                db, pending_uid,
                session.get('totp_pending_username') or '',
                session.get('totp_pending_next') or url_for('dashboard.index'),
            )
        flash('That code didn\'t match. Check your authenticator and try again.',
              'danger')

    return render_template('auth/totp.html')


def _clear_totp_pending():
    for key in ('totp_pending_user_id', 'totp_pending_username', 'totp_pending_next'):
        session.pop(key, None)


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
    # A valid invite (#274) opens registration even when it's otherwise closed,
    # and pins the email to the invited address. An SMS/WhatsApp invite (#272)
    # has a phone instead — invited_email stays None and the athlete enters
    # their own email normally.
    invite = lookup_invite(db, request.values.get('invite'))
    invite_token = invite['token'] if invite else None
    invited_email = invite['email'] if invite else None
    invited_phone = invite['phone'] if invite else None
    if not is_bootstrap and not _registration_open() and not invite:
        return ('Registration is closed.', 403)

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = invited_email or ((request.form.get('email') or '').strip() or None)
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
                                   is_bootstrap=is_bootstrap,
                                   invite_token=invite_token,
                                   invited_email=invited_email,
                                   invited_phone=invited_phone,
                                   signin_providers=pi.enabled_signin_providers())

        cur = db.execute(
            'INSERT INTO users (username, email, password_hash, display_name) '
            'VALUES (?,?,?,?) RETURNING id',
            (username, email, _hash_password(password), display_name)
        )
        new_user_id = cur.lastrowid
        # Commit the new user NOW, before any best-effort follow-up work, so the
        # account is durable regardless of what follows.
        #
        # The current_rx placeholder seed used to live here, sharing this
        # transaction: when it raised (e.g. the layer0 strength catalog not yet
        # built on this DB) Postgres aborted the transaction and the commit
        # silently rolled the user back — signup "succeeded" yet no account
        # existed. The seed is now done lazily on first /rx view
        # (routes.rx._ensure_current_rx_seeded), off the signup critical path
        # entirely: it only pre-fills "needs setup" rows, real rows are created
        # on demand when a session is logged, and deferring it means it runs
        # whenever the catalog is actually available rather than at the one
        # moment an account is being created.
        db.commit()

        if invite:
            # Invite acceptance proves control of the email (the link was
            # delivered to it and presented back), so the account starts
            # verified and the invite is marked used (#274).
            db.execute('UPDATE users SET email_verified = TRUE WHERE id = ?',
                       (new_user_id,))
            db.execute('UPDATE user_invites SET accepted_at = ?, '
                       'accepted_user_id = ? WHERE token = ?',
                       (datetime.utcnow().isoformat(timespec='seconds'),
                        new_user_id, invite_token))
            db.commit()
        elif email:
            # Confirm the email if one was given (#251). Best-effort: a mail
            # failure must not block registration — the athlete can resend from
            # account settings.
            try:
                send_verification_email(db, new_user_id, email)
            except Exception:
                pass

        session.clear()
        session['user_id'] = new_user_id
        session['username'] = username
        flash(f'Account created — welcome, {display_name or username}.', 'success')
        # v5 onboarding Step 2: drop new athletes on the connect screen
        # before the dashboard. The connect screen is itself skippable;
        # athletes who skip land on /profile?tab=athlete per
        # onboarding._POST_STEP2_TARGET. The route doesn't require any
        # special state (no `onboarded_at` flag) — existing athletes
        # hitting /onboarding/connect directly see the same surface as
        # a fresh signup, and can revisit any time.
        return redirect(url_for('onboarding.connect'))

    return render_template('auth/register.html',
                           username='', email=invited_email or '',
                           display_name='',
                           is_bootstrap=is_bootstrap,
                           invite_token=invite_token,
                           invited_email=invited_email,
                           invited_phone=invited_phone,
                           signin_providers=pi.enabled_signin_providers())


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
        '       u.username, u.display_name, u.email '
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
        # Recovery path for a lost authenticator (#265, Andy 2026-06-21): a
        # completed reset also clears any 2FA enrollment, so an athlete locked
        # out of their TOTP app gets back in via the email reset flow rather
        # than one-time backup codes. Proving control of the registered email
        # is the recovery factor. The athlete can re-enable 2FA from /profile
        # afterwards.
        mfa.disable(db, row['user_id'])
        db.commit()
        # Security receipt to the address on file. Best-effort: the reset is
        # already committed, so a notification fault must never fail it.
        try:
            send_password_changed_email(
                row['email'], row['display_name'] or row['username'])
        except Exception as exc:  # noqa: BLE001 — receipt must not break reset
            print(f'[email] password-changed receipt failed (reset): {exc}')
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
    html, text = render_email(
        'password-reset',
        display_name=display_name or 'there',
        reset_url=reset_url,
        expiry=f'{PASSWORD_RESET_TTL_MIN} minutes',
    )
    send_email(to_address, subject, text, html)


def send_password_changed_email(to_address: str, display_name: str) -> None:
    """Security receipt for a password change — reset completion (above) or an
    authenticated change from /profile (`profile.change_password`). Best-effort:
    callers swallow faults so a receipt problem never blocks the credential
    update, which is already committed by the time we get here."""
    if not to_address:
        return
    subject = 'AIDSTATION — your password was changed'
    html, text = render_email(
        'password-changed',
        display_name=display_name or 'there',
        timestamp=format_timestamp(),
        security_url=account_security_url(),
    )
    send_email(to_address, subject, text, html)


# ── Email verification ─────────────────────────────────────────────────────

def issue_email_verification(db, user_id: int, email: str) -> str:
    """Create a single-use, time-limited verification token for `email` and
    return it. Caller is responsible for actually sending the link (so the
    DB write is testable without a mail round-trip)."""
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=EMAIL_VERIFY_TTL_HOURS)
    db.execute(
        'INSERT INTO email_verifications (token, user_id, email, expires_at) '
        'VALUES (?,?,?,?)',
        (token, user_id, email, expires.isoformat(timespec='seconds')),
    )
    db.commit()
    return token


def consume_email_verification(db, token: str) -> tuple[str, int | None]:
    """Validate `token` and, on success, mark the user's email verified and the
    token used. Returns (status, user_id):

      - ('ok', uid)       — verified; flag flipped, token consumed.
      - ('invalid', None) — no such token.
      - ('used', uid)     — already consumed.
      - ('expired', uid)  — past its TTL.
      - ('stale', uid)    — the account's email changed since the token was
                            issued, so it no longer applies (don't verify a
                            stale address).

    No login required — possession of the token is the proof, exactly like the
    password-reset link.
    """
    row = db.execute(
        'SELECT ev.user_id, ev.email, ev.expires_at, ev.used_at, '
        '       u.email AS current_email '
        '  FROM email_verifications ev '
        '  JOIN users u ON u.id = ev.user_id '
        ' WHERE ev.token = ?',
        (token,),
    ).fetchone()
    if not row:
        return ('invalid', None)
    uid = row['user_id']
    if row['used_at']:
        return ('used', uid)
    expires_at = row['expires_at']
    expires_dt = (expires_at if isinstance(expires_at, datetime)
                  else datetime.fromisoformat(str(expires_at)))
    if expires_dt < datetime.utcnow():
        return ('expired', uid)
    # The token verifies one specific address; if the athlete has since changed
    # their email, this token is moot (a fresh one would've been issued).
    if (row['current_email'] or '').lower() != (row['email'] or '').lower():
        return ('stale', uid)
    db.execute('UPDATE users SET email_verified = TRUE WHERE id = ?', (uid,))
    db.execute('UPDATE email_verifications SET used_at = ? WHERE token = ?',
               (datetime.utcnow().isoformat(timespec='seconds'), token))
    db.commit()
    return ('ok', uid)


def send_verification_email(db, user_id: int, email: str) -> bool:
    """Issue a token and email the verification link. Returns True if the mail
    was put on the wire (False when email isn't configured — the link is still
    printed to logs by send_email's dev fallback). No-op (False) for a blank
    email."""
    if not email:
        return False
    token = issue_email_verification(db, user_id, email)
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    _send_verification_email(email, verify_url)
    print(f'[email-verify] issued user={user_id}')  # Rule #15 — no token logged
    return True


def _send_verification_email(to_address: str, verify_url: str) -> None:
    subject = 'AIDSTATION — confirm your email'
    html, text = render_email(
        'confirm-email',
        verify_url=verify_url,
        expiry=f'{EMAIL_VERIFY_TTL_HOURS} hours',
    )
    send_email(to_address, subject, text, html)


@bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    """Complete email verification from the link. Works logged-out (the token
    is the proof). Flips `users.email_verified` and lands the athlete on a
    sensible next screen with a flash."""
    db = get_db()
    status, _uid = consume_email_verification(db, token)
    messages = {
        'ok': ('Email confirmed. Thanks!', 'success'),
        'used': ('That link was already used — your email is confirmed.', 'info'),
        'expired': ('That confirmation link has expired. Request a new one from '
                    'your account settings.', 'warning'),
        'stale': ('That link was for a different email address. Request a new '
                  'one from your account settings.', 'warning'),
        'invalid': ('That confirmation link is invalid.', 'danger'),
    }
    msg, category = messages.get(status, messages['invalid'])
    flash(msg, category)
    if current_user_id():
        return redirect(url_for('profile.account_settings'))
    return redirect(url_for('auth.login'))


@bp.route('/verify/resend', methods=['POST'])
@_limit('5 per 15 minutes')
def resend_verification():
    """Re-send the verification link to the logged-in athlete's current email.
    Used from account settings and by athletes confirming a provider-seeded
    address."""
    db = get_db()
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))
    row = db.execute(
        'SELECT email, email_verified FROM users WHERE id = ?', (uid,)
    ).fetchone()
    if not row or not row['email']:
        flash('Add an email to your account first, then confirm it.', 'warning')
    elif row['email_verified']:
        flash('Your email is already confirmed.', 'info')
    else:
        send_verification_email(db, uid, row['email'])
        flash(f'Confirmation link sent to {row["email"]}. Check your inbox '
              f'(and spam folder).', 'info')
    return redirect(url_for('profile.account_settings'))


# ── Admin invites ──────────────────────────────────────────────────────────

def issue_invite(db, *, email: str | None = None, phone: str | None = None,
                  channel: str = 'email', created_by: int) -> str:
    """Create a single-use, time-limited invite token delivered via `channel`
    (#272 — 'email' | 'sms' | 'whatsapp'). Exactly one of `email`/`phone` is
    set, matching `channel`. Returns the token; caller sends the link.

    8-char token (48 bits, `token_urlsafe(6)`) rather than the 43-char default
    — short enough to read cleanly in an SMS, still computationally infeasible
    to guess against the existing `/auth/register` rate limit (10/hour/IP)
    within the 7-day `INVITE_TTL_DAYS` window."""
    token = secrets.token_urlsafe(6)
    expires = datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS)
    db.execute(
        'INSERT INTO user_invites (token, email, phone, channel, created_by, expires_at) '
        'VALUES (?,?,?,?,?,?)',
        (token, email, phone, channel, created_by, expires.isoformat(timespec='seconds')),
    )
    db.commit()
    return token


def lookup_invite(db, token):
    """Return the invite row if `token` is valid (exists, unaccepted,
    unexpired), else None. The gate for invite-only registration."""
    if not token:
        return None
    row = db.execute(
        'SELECT token, email, phone, channel, accepted_at, expires_at FROM user_invites '
        'WHERE token = ?', (token,)
    ).fetchone()
    if not row or row['accepted_at']:
        return None
    expires_at = row['expires_at']
    expires_dt = (expires_at if isinstance(expires_at, datetime)
                  else datetime.fromisoformat(str(expires_at)))
    if expires_dt < datetime.utcnow():
        return None
    return row


def _invite_url(token: str) -> str:
    """The short `/i/<token>` alias rather than `/auth/register?invite=...`
    directly — shorter to read in an SMS, and link-preview crawlers (iMessage,
    WhatsApp, Slack) follow the redirect and pick up register.html's og:*
    tags, so the preview card still shows the AIDSTATION brand image."""
    return url_for('invite_link.invite_redirect', token=token, _external=True)


def send_invite_email(db, email: str, created_by: int) -> str:
    """Issue an invite token and email the registration link. Returns the token
    (False-y send still logs the link via send_email's dev fallback)."""
    token = issue_invite(db, email=email, channel='email', created_by=created_by)
    _send_invite_email(email, _invite_url(token))
    print(f'[invite] issued via email to {email} by user={created_by}')  # Rule #15 — no token
    return token


def send_invite_sms(db, phone: str, created_by: int) -> str:
    """Issue an invite token and text the registration link via Twilio SMS
    (#272). Returns the token (False-y send still logs the link via
    sms_helper's dev fallback)."""
    token = issue_invite(db, phone=phone, channel='sms', created_by=created_by)
    send_sms(phone, _invite_text(_invite_url(token)))
    print(f'[invite] issued via sms to {phone} by user={created_by}')  # Rule #15 — no token
    return token


def send_invite_whatsapp(db, phone: str, created_by: int) -> str:
    """Issue an invite token and message the registration link via Twilio
    WhatsApp (#272). Returns the token (False-y send still logs the link via
    sms_helper's dev fallback)."""
    token = issue_invite(db, phone=phone, channel='whatsapp', created_by=created_by)
    send_whatsapp(phone, _invite_text(_invite_url(token)))
    print(f'[invite] issued via whatsapp to {phone} by user={created_by}')  # Rule #15 — no token
    return token


def _invite_text(invite_url: str) -> str:
    return (f"You're invited to AIDSTATION. Time to hit the trail — "
            f'create your account: {invite_url}\n'
            f'(Link expires in {INVITE_TTL_DAYS} days.)')


def _send_invite_email(to_address: str, invite_url: str) -> None:
    subject = "You're invited to AIDSTATION"
    text = (
        f"You've been invited to AIDSTATION. Time to hit the trail — "
        f'create your account here:\n\n'
        f'  {invite_url}\n\n'
        f'The link expires in {INVITE_TTL_DAYS} days.\n\n'
        f'— AIDSTATION\n'
    )
    html = f"""<!doctype html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#0E0F11;">
<p>You've been invited to AIDSTATION. Time to hit the trail.</p>
<p><a href="{invite_url}" style="display:inline-block;padding:10px 18px;background:#ED7A2D;color:#fff;text-decoration:none;border-radius:4px;">Create your account</a></p>
<p style="font-size:12px;color:#666;">Or paste this into your browser:<br><span style="font-family:ui-monospace,monospace;word-break:break-all;">{invite_url}</span></p>
<p style="font-size:12px;color:#666;">The link expires in {INVITE_TTL_DAYS} days.</p>
<p style="font-size:12px;color:#666;">— AIDSTATION</p>
</body></html>"""
    send_email(to_address, subject, text, html)


# ── Short invite links (#272 follow-up) ─────────────────────────────────────
# Separate, unprefixed blueprint so the link reads `/i/<token>` instead of
# `/auth/register?invite=<token>` — auth.bp is mounted at url_prefix='/auth',
# which a per-route override can't escape.

invite_link_bp = Blueprint('invite_link', __name__)


@invite_link_bp.route('/i/<token>')
def invite_redirect(token):
    """Redirect the short invite link to the real registration route. No DB
    lookup here — `register()` already validates the token (exists, unused,
    unexpired) and is rate-limited; this hop just keeps the shared link
    short."""
    return redirect(url_for('auth.register', invite=token))
