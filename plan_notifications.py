"""Plan-lifecycle notifications — email + in-app badge (#259 / #260).

When plan generation reaches a terminal status (`ready` or `failed`) in
`routes/plan_create.py::_advance_plan_generation`, the athlete gets:

1. **Email** (best-effort, via `email_helper.send_email`) — "your plan is
   ready" / "your plan couldn't be generated".
2. **In-app badge** — a dashboard banner that reads the same `plan_versions`
   columns and is dismissed by stamping `notification_seen_at`.

Both the progress-screen poller and the every-minute cron drive the terminal
transition, so a naive "send on terminal" would double-send. The guard is an
ATOMIC claim on `plan_versions.notified_at` (`claim_terminal_notification`):
the first writer to flip it from NULL → NOW() wins and sends; a racing second
pass matches 0 rows and no-ops. The claim is keyed on the row, so it holds
across the poller/cron race AND across separate serverless invocations — the
per-process state a Python flag would use is useless here.

Everything is best-effort: a notification fault must NEVER break generation
(the plan is already durable + terminal before any of this runs), so the entry
point swallows every exception and only logs. The badge read degrades to an
empty list on any fault, mirroring `active_nudges` (app.py).

PG-only — these columns live in `_PG_MIGRATIONS`; SQLite dev never exercises
this path (plan generation is Postgres-only).
"""

from __future__ import annotations

from email_helper import send_email
from email_templates import render_email, public_base_url
from notification_prefs import type_for_plan_status as notif_type_for_plan_status
from plan_naming import generated_plan_name, target_race_name


def _email_channel_enabled(db, user_id: int, type_key: str) -> bool:
    """True iff the athlete wants email for this notification type (#963).

    Thin best-effort wrapper over the preference repo: a missing table (SQLite
    dev) or any read fault fails open to the registry default (send), so the
    email path is deploy-safe before the preference store lands and a store
    hiccup never suppresses a real notification."""
    try:
        from notification_preferences_repo import channel_enabled
        return channel_enabled(db, user_id, type_key, 'email')
    except Exception as exc:  # noqa: BLE001 — fail open to the default (send)
        print(f"_email_channel_enabled: pref read failed, sending anyway: {exc}")
        return True


def claim_terminal_notification(db, user_id: int, plan_version_id: int) -> bool:
    """Atomically claim the one-shot terminal notification for this plan.

    Flips `notified_at` from NULL → NOW() in a single conditional UPDATE,
    scoped to `(id, user_id)` and gated on the row being terminal. The
    `RETURNING id` makes the win observable: exactly one writer gets a row
    back, every racing pass (and any later re-poll of the already-notified
    row) gets None. Commits so the claim is durable before the caller sends.

    Returns True iff THIS call won the claim (and should send the email).
    """
    won = db.execute(
        "UPDATE plan_versions SET notified_at = NOW() "
        "WHERE id = ? AND user_id = ? AND notified_at IS NULL "
        "AND generation_status IN ('ready', 'failed') "
        "RETURNING id",
        (plan_version_id, user_id),
    ).fetchone()
    db.commit()
    return won is not None


def _plan_display_name(db, user_id: int, plan_version: dict) -> str:
    """The athlete-facing plan label, matching the plans list / header / badge
    (#620). Best-effort — any read miss degrades to the plain fallback."""
    try:
        return generated_plan_name(
            target_race_name(db, user_id),
            plan_version.get('scope_start_date'),
            plan_version.get('scope_end_date'),
        )
    except Exception:  # noqa: BLE001 — a name miss must not skip the notification
        return 'Training plan'


def _plan_url(plan_version_id: int, status: str) -> str | None:
    """Absolute URL for the email CTA. `ready` deep-links to the plan view;
    `failed` lands on the create form to retry (the view redirects there with
    the error anyway). Built best-effort: outside a request context (or with no
    SERVER_NAME) `url_for(_external=True)` raises, so we degrade to no link and
    the email simply tells the athlete to open AIDSTATION."""
    try:
        from flask import url_for
        if status == 'ready':
            return url_for('plan_create.view_plan',
                           plan_version_id=plan_version_id, _external=True)
        return url_for('plan_create.new_plan', _external=True)
    except Exception:  # noqa: BLE001 — no-URL email is still useful
        return None


def build_notification_email(
    status: str, plan_name: str, display_name: str,
    plan_url: str | None, error_message: str | None,
) -> tuple[str, str, str]:
    """Return `(subject, text_body, html_body)` for a terminal-status email.

    `status` is 'ready' or 'failed'. For 'failed', `error_message` is the
    user-facing copy already on `generation_error`. `plan_url` may be None (no
    request context to build it) — the shared template always renders a CTA, so
    we fall back to the app origin for the button target.
    """
    name = display_name or 'athlete'
    cta_url = plan_url or public_base_url()
    if status == 'ready':
        subject = f'AIDSTATION — your plan "{plan_name}" is ready'
        html_body, text_body = render_email(
            'plan-ready', display_name=name, plan_name=plan_name,
            plan_url=cta_url,
        )
    else:
        subject = f'AIDSTATION — couldn\'t generate "{plan_name}"'
        detail = error_message or 'Plan generation failed. Please try again.'
        html_body, text_body = render_email(
            'plan-failed', display_name=name, plan_name=plan_name,
            error_message=detail, retry_url=cta_url,
        )
    return subject, text_body, html_body


def notify_plan_terminal(db, user_id: int, plan_version_id: int,
                         plan_version: dict) -> bool:
    """Fire the email + arm the in-app badge for a plan that just reached a
    terminal status. Call this AFTER the `ready`/`failed` status is committed.

    Single-fire across the poller/cron race via `claim_terminal_notification`:
    if this call doesn't win the atomic claim, it's a no-op. The in-app badge is
    armed by the same claim (the dashboard reads `notified_at`/
    `notification_seen_at`), so it shows even if the email can't be sent.

    Fully best-effort — every fault is caught + logged so a notification
    problem can NEVER turn the (already-committed) terminal path into a 500.
    Returns True iff this call won the claim and attempted delivery.
    """
    try:
        status = plan_version.get('generation_status')
        if status not in ('ready', 'failed'):
            return False
        if not claim_terminal_notification(db, user_id, plan_version_id):
            # Another pass (poller or cron) already notified this row.
            return False

        # Badge is now armed regardless of what happens below. Send the email
        # best-effort — a missing address or a SendGrid hiccup just means no
        # mail; the in-app badge still surfaces the outcome.
        row = db.execute(
            "SELECT email, display_name, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        to_address = (row.get('email') if row else None) or ''
        if not to_address.strip():
            print(
                f"notify_plan_terminal: no email on file for user_id={user_id} "
                f"(plan_version_id={plan_version_id}); in-app badge only"
            )
            return True

        # Honour the athlete's per-type email opt-in (#963). Fails open to the
        # registry default (send) on any preference-store fault — a pref hiccup
        # must never silently swallow a plan-lifecycle email. In-app delivery is
        # gated separately at badge-read time (get_unseen_plan_notifications).
        type_key = notif_type_for_plan_status(status)
        if type_key and not _email_channel_enabled(db, user_id, type_key):
            print(
                f"notify_plan_terminal: email opted out for {type_key} "
                f"(plan_version_id={plan_version_id} user_id={user_id}); "
                f"in-app badge only"
            )
            return True

        display_name = (
            (row.get('display_name') or row.get('username') or '') if row else ''
        ).strip()
        plan_name = _plan_display_name(db, user_id, plan_version)
        subject, text_body, html_body = build_notification_email(
            status,
            plan_name,
            display_name,
            _plan_url(plan_version_id, status),
            plan_version.get('generation_error'),
        )
        sent = send_email(to_address, subject, text_body, html_body)
        # `sent` is False when SendGrid is unconfigured (stdout fallback) or
        # rejected the send (e.g. an unverified EMAIL_FROM_ADDRESS) — the in-app
        # badge is armed either way. Surfacing the outcome here lets prod logs
        # confirm a real send per plan, not just that we reached dispatch.
        print(
            f"notify_plan_terminal: {status} notification for "
            f"plan_version_id={plan_version_id} user_id={user_id} "
            f"(email_sent={sent}; in-app badge armed)"
        )
        return True
    except Exception as exc:  # noqa: BLE001 — notification must not break generation
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        print(
            f"notify_plan_terminal: non-fatal notification failure for "
            f"plan_version_id={plan_version_id} user_id={user_id}: {exc}"
        )
        return False


def get_unseen_plan_notifications(db, user_id: int) -> list[dict]:
    """Undismissed terminal-plan notifications for `user_id`, newest first —
    the dashboard in-app badge feed.

    Returns one decorated dict per row: `id`, `status` ('ready'/'failed'),
    `plan_name`, `error` (failed only), and `category` ('good'/'bad') for the
    banner styling. Empty when `user_id` is falsy so the caller needn't
    special-case logged-out renders. Gated on `notified_at IS NOT NULL` so
    legacy `ready`-by-default rows (which never fired a notification) never
    badge.
    """
    if not user_id:
        return []
    rows = db.execute(
        "SELECT id, generation_status, generation_error, "
        "scope_start_date, scope_end_date "
        "FROM plan_versions "
        "WHERE user_id = ? AND notified_at IS NOT NULL "
        "AND notification_seen_at IS NULL "
        "AND generation_status IN ('ready', 'failed') "
        "ORDER BY notified_at DESC",
        (user_id,),
    ).fetchall()
    # Honour an explicit in-app opt-out per notification type (#963). Only a
    # stored `enabled = FALSE` suppresses the badge; the default (no row) keeps
    # showing it. One small read, fail-closed to the empty set so a store fault
    # never hides notifications.
    try:
        from notification_preferences_repo import disabled_in_app_types
        muted = disabled_in_app_types(db, user_id)
    except Exception as exc:  # noqa: BLE001 — suppress nothing on a read fault
        print(f"get_unseen_plan_notifications: in_app gate read failed: {exc}")
        muted = set()
    out = []
    for r in rows:
        status = r['generation_status']
        if notif_type_for_plan_status(status) in muted:
            continue
        out.append({
            'id': r['id'],
            'status': status,
            'plan_name': _plan_display_name(db, user_id, {
                'scope_start_date': r['scope_start_date'],
                'scope_end_date': r['scope_end_date'],
            }),
            'error': r['generation_error'] if status == 'failed' else None,
            'category': 'good' if status == 'ready' else 'bad',
        })
    return out


def mark_plan_notification_seen(db, user_id: int, plan_version_id: int) -> None:
    """Dismiss the in-app badge for one plan by stamping
    `notification_seen_at`. Scoped to `(id, user_id)` so a crafted request for
    another athlete's plan is a no-op. Idempotent (only stamps an unstamped,
    already-notified row)."""
    db.execute(
        "UPDATE plan_versions SET notification_seen_at = NOW() "
        "WHERE id = ? AND user_id = ? AND notified_at IS NOT NULL "
        "AND notification_seen_at IS NULL",
        (plan_version_id, user_id),
    )
    db.commit()
