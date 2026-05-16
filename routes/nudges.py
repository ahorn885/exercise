"""14-day connect-provider nudge + dismissable banner plumbing (v5 §A.2.4).

PR9 / Option E of the v5 onboarding implementation arc. Closes the last
unshipped v5 onboarding mechanic: athletes who skip provider connection
at Step 2 (or just don't connect anything within 14 days) see a single
passive in-app banner pointing them at `/onboarding/connect`. Dismissable;
one-shot, no escalation. Stored as a row in `account_nudges` with
`nudge_type='connect_provider_14d'`. UNIQUE on `(user_id, nudge_type)`
makes the scanner idempotent — re-runs INSERT … ON CONFLICT DO NOTHING.

Two surfaces:

1. `GET /cron/nudges/connect_provider_14d` — token-gated daily scanner.
   Vercel Cron hits this with `Authorization: Bearer $CRON_SECRET`.
   Inserts one row per eligible user (account >= 14 days old AND zero
   `provider_auth.status='active'` rows AND no existing nudge of this
   type). Returns JSON `{inserted: N}`. Idempotent.

2. `POST /nudges/<int:nudge_id>/dismiss` — athlete clicks the banner's
   close button; writes `dismissed_at`, redirects back to referrer.

The banner partial (`templates/_account_nudges.html`) reads the result
of `get_active_nudges(db, uid)` via the `active_nudges` template
context processor in `app.py`. PG-only — `account_nudges` is in
`_PG_MIGRATIONS` only; SQLite dev returns [] and renders nothing.
"""

import hmac
import os

from flask import (
    Blueprint, request, redirect, url_for, abort, jsonify,
)

from database import get_db
from routes.auth import current_user_id


bp = Blueprint('nudges', __name__)


# Per-`nudge_type` UI metadata. The banner partial reads this overlay
# from `get_active_nudges`; adding a new nudge_type means adding an
# entry here (and a writer somewhere that inserts the row).
NUDGE_REGISTRY = {
    'connect_provider_14d': {
        'message': (
            'AIDSTATION works best with a fitness provider connected. '
            'Want to set one up?'
        ),
        'cta_label': 'Connect a provider',
        'cta_endpoint': 'onboarding.connect',
        'category': 'info',
    },
}


def get_active_nudges(db, uid):
    """Return undismissed nudges for `uid`, newest first.

    Each entry: dict with `id`, `nudge_type`, `created_at`, plus the
    registry overlay (message / cta_label / cta_endpoint / category).
    Unknown nudge_types fall back to the raw `nudge_type` as the
    message — a future writer that lands a new type before this
    registry catches up produces an ugly-but-visible banner rather
    than a silent miss.

    Empty when `uid` is falsy so the context processor is safe to call
    on logged-out pages.
    """
    if not uid:
        return []
    rows = db.execute(
        'SELECT id, nudge_type, created_at FROM account_nudges '
        'WHERE user_id = ? AND dismissed_at IS NULL '
        'ORDER BY created_at DESC',
        (uid,),
    ).fetchall()
    out = []
    for r in rows:
        entry = NUDGE_REGISTRY.get(r['nudge_type'], {
            'message': r['nudge_type'],
            'cta_label': None,
            'cta_endpoint': None,
            'category': 'info',
        })
        out.append({
            'id': r['id'],
            'nudge_type': r['nudge_type'],
            'created_at': r['created_at'],
            **entry,
        })
    return out


def _cron_authorized():
    """True iff the request carries `Authorization: Bearer $CRON_SECRET`.

    Vercel Cron sends this header automatically once `CRON_SECRET` is
    set in the project env. Constant-time compare via `hmac.compare_digest`
    guards against timing side-channels. Returns False when CRON_SECRET
    isn't set so a misconfigured production deploy fails closed.
    """
    expected = os.environ.get('CRON_SECRET') or ''
    if not expected:
        return False
    header = request.headers.get('Authorization') or ''
    prefix = 'Bearer '
    if not header.startswith(prefix):
        return False
    received = header[len(prefix):]
    return hmac.compare_digest(received, expected)


@bp.route('/cron/nudges/connect_provider_14d', methods=['GET'])
def scan_connect_provider_14d():
    """Daily scan: insert one nudge row per eligible user.

    Eligibility per v5 §A.2.4:
      - `users.created_at <= NOW() - INTERVAL '14 days'`
        (NULL created_at — legacy rows pre-dating the column default —
        counts as old enough; safer than skipping silently)
      - zero `provider_auth` rows with `status='active'` for this user
      - no existing `account_nudges` row with this `nudge_type`
        (covers both un-dismissed and already-dismissed: one shot ever)

    Single SQL statement does the eligibility filter + insert. ON
    CONFLICT DO NOTHING covers the rare race where a second cron run
    overlaps (re-running the scanner is otherwise idempotent on its
    own NOT EXISTS guard).

    Returns JSON `{inserted: N}`.
    """
    if not _cron_authorized():
        abort(401)
    db = get_db()
    cur = db.execute(
        '''
        INSERT INTO account_nudges (user_id, nudge_type)
        SELECT u.id, 'connect_provider_14d'
        FROM users u
        WHERE (u.created_at IS NULL OR u.created_at <= NOW() - INTERVAL '14 days')
          AND NOT EXISTS (
              SELECT 1 FROM provider_auth pa
              WHERE pa.user_id = u.id AND pa.status = 'active'
          )
          AND NOT EXISTS (
              SELECT 1 FROM account_nudges an
              WHERE an.user_id = u.id AND an.nudge_type = 'connect_provider_14d'
          )
        ON CONFLICT (user_id, nudge_type) DO NOTHING
        RETURNING id
        '''
    )
    inserted = len(cur.fetchall())
    db.commit()
    return jsonify(inserted=inserted), 200


@bp.route('/nudges/<int:nudge_id>/dismiss', methods=['POST'])
def dismiss(nudge_id):
    """Mark a nudge dismissed. Scoped to the logged-in user — the UPDATE
    matches on `(id, user_id)` so a crafted POST targeting another
    athlete's nudge_id is a no-op. Redirects back to the referrer
    (banner can appear on any page) with a dashboard fallback.
    """
    db = get_db()
    uid = current_user_id()
    db.execute(
        'UPDATE account_nudges SET dismissed_at = NOW() '
        'WHERE id = ? AND user_id = ?',
        (nudge_id, uid),
    )
    db.commit()
    return redirect(request.referrer or url_for('dashboard.index'))
