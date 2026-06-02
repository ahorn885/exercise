"""Account-nudge banner plumbing (v5 §A.2.4 + D-66 onboarding skip nudges).

Two writer patterns now feed `account_nudges`:

1. **Insert-delayed** (PR9 / `connect_provider_14d`): cron INSERTs the
   row 14 days after account creation. Banner displays immediately on
   the next page load. No display-delay applied on read.
2. **Insert-immediate, display-delayed** (D-66 onboarding skip nudges
   `target_race_skipped` + `route_locales_incomplete`): the skip
   handler in `routes/onboarding.py` writes the row at skip-time
   (synchronous with the athlete's click). The banner is suppressed by
   `get_active_nudges` until `display_delay_days` have elapsed since
   `created_at` — gives the athlete a grace window before nudging.

The registry entry per-nudge_type declares which pattern applies via
`display_delay_days` (default 0 — banner displays as soon as the row
exists). Both patterns coexist because PR9's 14-day-after-account-age
eligibility is a property of the candidate population (a wider-than-14d
account that lacks any provider), whereas D-66's 14-day-after-skip
delay is a property of the individual nudge event (gives the athlete
time to come back on their own before reminding).

Surfaces:

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

from datetime import datetime, timezone

from flask import (
    Blueprint, request, redirect, url_for, abort, jsonify, render_template,
)

from database import get_db
from routes.auth import cron_authorized, current_user_id


bp = Blueprint('nudges', __name__)


# Per-`nudge_type` UI metadata. The banner partial reads this overlay
# from `get_active_nudges`; adding a new nudge_type means adding an
# entry here (and a writer somewhere that inserts the row).
#
# `display_delay_days` (optional, default 0) suppresses the banner
# until that many days have elapsed since `created_at`. Use a nonzero
# value when the row is written synchronously with the trigger event
# (e.g., D-66 onboarding skip nudges) and the athlete should get a
# grace window before being reminded. Leave at 0 (default) when the
# writer already gated insertion on a time condition (e.g., PR9's
# cron that only inserts after 14 days of account age).
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
    'target_race_skipped': {
        'message': (
            "You skipped picking a target race during onboarding. "
            "Adding one unlocks race-week brief generation."
        ),
        'cta_label': 'Set a target race',
        'cta_endpoint': 'onboarding.target_race',
        'category': 'info',
        'display_delay_days': 14,
    },
    'route_locales_incomplete': {
        'message': (
            "Your target race is multi-day but the route locales aren't "
            "filled in yet. Add start/finish + aid stations so your "
            "race-week brief can include per-segment pacing + kit."
        ),
        'cta_label': 'Add route locales',
        'cta_endpoint': 'onboarding.route_locales',
        'category': 'info',
        'display_delay_days': 14,
    },
}


def _past_display_delay(created_at, delay_days):
    """True iff `created_at` is at least `delay_days` days in the past.

    Treats null `created_at` (legacy rows pre-dating the column default)
    as "very old" so display proceeds — fail-open mirrors the cron-side
    null handling. `delay_days` of 0 always returns True (no delay).
    The `account_nudges.created_at` column is `TIMESTAMP` (naive) per
    init_db.py; we attach UTC to compare safely against `datetime.now`.
    """
    if delay_days <= 0:
        return True
    if created_at is None:
        return True
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created_at).days >= delay_days


def get_active_nudges(db, uid):
    """Return undismissed nudges for `uid`, newest first.

    Each entry: dict with `id`, `nudge_type`, `created_at`, plus the
    registry overlay (message / cta_label / cta_endpoint / category).
    Unknown nudge_types fall back to the raw `nudge_type` as the
    message — a future writer that lands a new type before this
    registry catches up produces an ugly-but-visible banner rather
    than a silent miss.

    Nudges with `display_delay_days` set in the registry are suppressed
    until that many days after `created_at`. Unknown nudge_types
    inherit the 0-delay default (display immediately) since we don't
    know the writer pattern.

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
        if not _past_display_delay(r['created_at'], entry.get('display_delay_days', 0)):
            continue
        out.append({
            'id': r['id'],
            'nudge_type': r['nudge_type'],
            'created_at': r['created_at'],
            **{k: v for k, v in entry.items() if k != 'display_delay_days'},
        })
    return out


def _feed_overlay(row):
    """Registry overlay for one `account_nudges` row, for the feed page.

    Same visible-but-ugly-never-silent posture as `get_active_nudges`:
    unknown nudge_types fall back to the raw `nudge_type` as the
    message. Strips `display_delay_days` — a banner-only implementation
    detail the feed template has no use for.
    """
    entry = NUDGE_REGISTRY.get(row['nudge_type'], {
        'message': row['nudge_type'],
        'cta_label': None,
        'cta_endpoint': None,
        'category': 'info',
    })
    return {
        'id': row['id'],
        'nudge_type': row['nudge_type'],
        'created_at': row['created_at'],
        **{k: v for k, v in entry.items() if k != 'display_delay_days'},
    }


def get_feed_nudges(db, uid):
    """Return `(new, earlier)` decorated nudge lists for the §21 feed.

    `new` mirrors the banner exactly — undismissed rows past their
    display delay (reuses `get_active_nudges`, so the feed and the
    banner can never disagree about what's "live"). `earlier` is every
    dismissed row, most-recently-dismissed first, each carrying its
    `dismissed_at`. Scheduled-but-not-yet-due nudges (undismissed but
    still inside their grace window) are in neither list — they aren't
    surfaced anywhere until the delay elapses.

    Empty lists when `uid` is falsy so callers needn't special-case the
    logged-out path. PG-only table — SQLite dev raises on the SELECT;
    the route wraps this call and degrades to an empty feed.
    """
    if not uid:
        return [], []
    new = get_active_nudges(db, uid)
    rows = db.execute(
        'SELECT id, nudge_type, created_at, dismissed_at FROM account_nudges '
        'WHERE user_id = ? AND dismissed_at IS NOT NULL '
        'ORDER BY dismissed_at DESC',
        (uid,),
    ).fetchall()
    earlier = []
    for r in rows:
        item = _feed_overlay(r)
        item['dismissed_at'] = r['dismissed_at']
        earlier.append(item)
    return new, earlier


@bp.route('/notifications', methods=['GET'])
def feed():
    """Full notifications feed (v5 §21).

    Two sections: **New** (undismissed, banner-visible nudges — each
    rendered with its registry CTA deep-link + an inline dismiss form)
    and **Earlier** (previously dismissed, read-only). The full-page
    companion to the passive banner (`_account_nudges.html`) and the
    topbar bell dropdown.

    Fail-open to an empty feed if the read raises — e.g. SQLite dev,
    where `account_nudges` lives only in `_PG_MIGRATIONS` — so the page
    renders rather than 500s, mirroring the `active_nudges` context
    processor in app.py.
    """
    uid = current_user_id()
    try:
        new, earlier = get_feed_nudges(get_db(), uid)
    except Exception as e:  # noqa: BLE001 — degrade to empty, never 500
        print(f'nudges: get_feed_nudges failed: {e}')
        new, earlier = [], []
    return render_template('nudges/feed.html', new=new, earlier=earlier)


# Delivery channels surfaced on the §22 settings page. Read-only — these
# describe how notifications actually ship today, not configurable prefs.
NOTIFICATION_CHANNELS = [
    {
        'label': 'In-app',
        'status': 'On',
        'detail': 'Passive banner + the notifications feed. Dismiss any '
                  'item individually — that is the only per-notification '
                  'control today.',
    },
    {
        'label': 'Email',
        'status': 'Account-critical only',
        'detail': 'Transactional messages such as password resets. No '
                  'digests or marketing — nothing to opt out of.',
    },
]


@bp.route('/notifications/settings', methods=['GET'])
def settings():
    """Notification settings (v5 §22) — read-only by design.

    There is no per-channel / per-category preference store today: the
    only athlete-facing control is dismissing an individual in-app
    nudge, which §21's feed already provides. Rather than fabricate
    toggles with nowhere to write, this page honestly documents the
    delivery model — the same posture as §17 Connections › Preferences.

    The reminder list is derived live from `NUDGE_REGISTRY` so it can
    never drift from what actually ships. Each entry carries the same
    registry overlay the banner/feed use (message + category).
    """
    reminders = [
        {'nudge_type': k, 'message': v['message'], 'category': v['category']}
        for k, v in NUDGE_REGISTRY.items()
    ]
    return render_template('nudges/settings.html',
                           channels=NOTIFICATION_CHANNELS,
                           reminders=reminders)


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
    if not cron_authorized():
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
