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
    flash,
)

import notification_prefs
from database import get_db
from notification_preferences_repo import (
    build_matrix, disabled_in_app_types, save_from_form,
)
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
# `notification_type` (optional, default 'account_reminders') maps the
# nudge_type onto a `notification_prefs.NOTIFICATION_TYPES` key so the §22
# settings matrix can gate in-app display per type (see `get_active_nudges`).
# The onboarding/connect nudges all roll up under the catch-all
# 'account_reminders' toggle; the #964 reminder/staleness nudges each carry
# their own type so they can be muted independently.
NUDGE_REGISTRY = {
    'connect_provider_14d': {
        'message': (
            'AIDSTATION works best with a fitness provider connected. '
            'Want to set one up?'
        ),
        'cta_label': 'Connect a provider',
        'cta_endpoint': 'onboarding.connect',
        'category': 'info',
        'notification_type': 'account_reminders',
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
        'notification_type': 'account_reminders',
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
        'notification_type': 'account_reminders',
    },
    # ─── #964 reminder / staleness nudges ───────────────────────────────────
    # Reconciled daily by `scan_reconcile_staleness`: the row is inserted while
    # the condition holds and DELETED once it clears, so the nudge can re-fire
    # on a later recurrence (a plain one-shot insert is blocked forever by the
    # `UNIQUE (user_id, nudge_type)` constraint). Each maps to its own §22
    # notification type so it can be muted independently.
    'log_reminder': {
        'message': (
            "You haven't logged a workout in a few days. Keep your training "
            'record current so your plan and progress stay accurate.'
        ),
        'cta_label': 'Log a workout',
        'cta_endpoint': 'log.index',
        'category': 'info',
        'notification_type': 'log_reminder',
    },
    'body_metric_stale': {
        'message': (
            "Your body metrics haven't been refreshed in a while. A quick "
            'weight / body update keeps your plan calibrated.'
        ),
        'cta_label': 'Update body metrics',
        'cta_endpoint': 'body.list_entries',
        'category': 'info',
        'notification_type': 'body_metric_stale',
    },
    'injury_review': {
        'message': (
            "One of your injuries has been marked active for a while. Still "
            'bothering you? Update its status or resolve it.'
        ),
        'cta_label': 'Review injuries',
        'cta_endpoint': 'injuries.list_entries',
        'category': 'info',
        'notification_type': 'injury_review',
    },
    # A plan parked at the Layer 3D HITL review gate (#213) never finishes until
    # the athlete resolves it. `warning` styling — this blocks a plan, unlike the
    # passive `info` staleness nudges above.
    'plan_needs_review': {
        'message': (
            'A plan you started is waiting on your review before it can '
            'finish. Resolve its open items to complete it.'
        ),
        'cta_label': 'Review your plan',
        'cta_endpoint': 'plans.list_plans',
        'category': 'warning',
        'notification_type': 'plan_needs_review',
    },
}

# Registry knobs that are internal plumbing, stripped from the per-row overlay
# the feed / banner templates consume (kept stable so the template context
# surface doesn't grow as we add delay-bearing or preference-linked entries).
_INTERNAL_REGISTRY_KEYS = ('display_delay_days', 'notification_type')


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

    Per-type in-app delivery preferences (#963/#964) are honoured: a nudge
    whose mapped `notification_type` has been explicitly turned off for the
    in_app channel is suppressed. The preference read fails **open** (suppress
    nothing) on any fault, so a store hiccup never hides a nudge. Unknown
    nudge_types roll up under the catch-all 'account_reminders' type.

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
    try:
        muted = disabled_in_app_types(db, uid)
    except Exception as e:  # noqa: BLE001 — suppress nothing on a read fault
        print(f'nudges: in_app preference gate read failed: {e}')
        muted = set()
    out = []
    for r in rows:
        entry = NUDGE_REGISTRY.get(r['nudge_type'], {
            'message': r['nudge_type'],
            'cta_label': None,
            'cta_endpoint': None,
            'category': 'info',
        })
        if entry.get('notification_type', 'account_reminders') in muted:
            continue
        if not _past_display_delay(r['created_at'], entry.get('display_delay_days', 0)):
            continue
        out.append({
            'id': r['id'],
            'nudge_type': r['nudge_type'],
            'created_at': r['created_at'],
            **{k: v for k, v in entry.items()
               if k not in _INTERNAL_REGISTRY_KEYS},
        })
    return out


def _feed_overlay(row):
    """Registry overlay for one `account_nudges` row, for the feed page.

    Same visible-but-ugly-never-silent posture as `get_active_nudges`:
    unknown nudge_types fall back to the raw `nudge_type` as the
    message. Strips internal registry knobs (`display_delay_days`,
    `notification_type`) — plumbing the feed template has no use for.
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
        **{k: v for k, v in entry.items()
           if k not in _INTERNAL_REGISTRY_KEYS},
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

    Each `new` item also carries `read_at` (#963): read/unread is orthogonal
    to dismiss — an undismissed nudge can be unread (read_at NULL) or read. The
    read state is hydrated with one small extra read over the same undismissed
    set; a fault there degrades to "all unread" rather than dropping the item.

    Empty lists when `uid` is falsy so callers needn't special-case the
    logged-out path. PG-only table — SQLite dev raises on the SELECT;
    the route wraps this call and degrades to an empty feed.
    """
    if not uid:
        return [], []
    new = get_active_nudges(db, uid)
    # Hydrate read_at for the undismissed set (read/unread). Kept off
    # get_active_nudges so the banner/context-processor read stays untouched.
    read_map: dict = {}
    try:
        for r in db.execute(
            'SELECT id, read_at FROM account_nudges '
            'WHERE user_id = ? AND dismissed_at IS NULL',
            (uid,),
        ).fetchall():
            read_map[r['id']] = r['read_at']
    except Exception as e:  # noqa: BLE001 — fall back to all-unread
        print(f'nudges: read_at hydrate failed: {e}')
    for item in new:
        item['read_at'] = read_map.get(item['id'])
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
    unread_count = sum(1 for n in new if not n.get('read_at'))
    return render_template('nudges/feed.html', new=new, earlier=earlier,
                           unread_count=unread_count)


@bp.route('/notifications/settings', methods=['GET', 'POST'])
def settings():
    """Notification settings (v5 §22 / #963) — the per-type × per-channel
    delivery-preference matrix.

    GET renders a toggle for every applicable `(notification_type, channel)`
    cell, resolved from `notification_preferences` over the registry defaults
    (`notification_prefs`). POST persists the whole submit
    (`save_from_form`) — unchecked boxes don't post, so the off state is
    captured by iterating the registry, not the form.

    `push` toggles render but carry an "arrives with the app" note: the
    preference is stored now, delivery lands later (#963). The page degrades to
    the shipped defaults if the override read faults (e.g. SQLite dev), so it
    always renders rather than 500ing — mirroring the feed's posture.
    """
    db = get_db()
    uid = current_user_id()
    if request.method == 'POST':
        try:
            n = save_from_form(db, uid, request.form)
            flash(f'Notification preferences saved ({n} updated).', 'success')
        except Exception as e:  # noqa: BLE001 — surface, don't 500
            print(f'nudges: save_from_form failed: {e}')
            flash('Could not save notification preferences. Please try again.',
                  'error')
        return redirect(url_for('nudges.settings'))
    matrix = build_matrix(db, uid)
    return render_template('nudges/settings.html',
                           channels=notification_prefs.CHANNELS,
                           matrix=matrix)


@bp.route('/nudges/<int:nudge_id>/read', methods=['POST'])
def mark_read(nudge_id):
    """Mark one notification read (#963). Scoped to the logged-in user and
    idempotent (only stamps an unread, undismissed row). Redirects back to the
    feed."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        'UPDATE account_nudges SET read_at = NOW() '
        'WHERE id = ? AND user_id = ? AND read_at IS NULL',
        (nudge_id, uid),
    )
    db.commit()
    return redirect(request.referrer or url_for('nudges.feed'))


@bp.route('/nudges/read-all', methods=['POST'])
def mark_all_read():
    """Mark every undismissed, unread notification read in one click (#963).
    User-scoped; a no-op when nothing is unread. Redirects back to the feed."""
    db = get_db()
    uid = current_user_id()
    db.execute(
        'UPDATE account_nudges SET read_at = NOW() '
        'WHERE user_id = ? AND dismissed_at IS NULL AND read_at IS NULL',
        (uid,),
    )
    db.commit()
    return redirect(request.referrer or url_for('nudges.feed'))


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


# ─── #964 reminder / staleness reconcile ────────────────────────────────────
#
# Staleness thresholds (days). Tuned conservative so the feed nudges, not nags.
LOG_STALE_DAYS = 5            # no workout logged in this window ⇒ log_reminder
LOG_MIN_ACCOUNT_DAYS = 7      # skip brand-new accounts still onboarding
BODY_STALE_DAYS = 30          # no body-metric entry in this window ⇒ refresh
BODY_MIN_ACCOUNT_DAYS = 14
INJURY_REVIEW_DAYS = 30       # injury active+untouched this long ⇒ review
PLAN_REVIEW_STALE_DAYS = 3    # plan parked at the review gate this long ⇒ nudge

# Per-type reconcile spec. Each entry pairs the INSERT that ARMS the nudge while
# its condition holds with the DELETE that CLEARS it once the condition lifts —
# the delete is what lets a one-shot-`UNIQUE`-constrained row re-fire on a later
# recurrence (e.g. log → go stale again → nudge again). `date`/`start_date` are
# ISO-text columns, so the `TO_CHAR(... 'YYYY-MM-DD')` cutoff compares correctly
# lexicographically. Both statements `RETURNING id` so the route can count rows.
#
# PG-only (TO_CHAR / INTERVAL / ON CONFLICT). The endpoint is token-gated and
# only fires on the deployed Postgres; SQLite dev never reaches it.
_STALENESS_RECONCILE = [
    {
        'nudge_type': 'log_reminder',
        # Account past onboarding AND nothing logged (strength or cardio) in
        # the window. A connected provider's auto-imports keep cardio_log
        # fresh, so synced athletes are naturally excluded.
        'insert': f'''
            INSERT INTO account_nudges (user_id, nudge_type)
            SELECT u.id, 'log_reminder'
            FROM users u
            WHERE (u.created_at IS NULL
                   OR u.created_at <= NOW() - INTERVAL '{LOG_MIN_ACCOUNT_DAYS} days')
              AND NOT EXISTS (
                  SELECT 1 FROM training_log tl WHERE tl.user_id = u.id
                    AND tl.date >= TO_CHAR(NOW() - INTERVAL '{LOG_STALE_DAYS} days', 'YYYY-MM-DD')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM cardio_log cl WHERE cl.user_id = u.id
                    AND cl.date >= TO_CHAR(NOW() - INTERVAL '{LOG_STALE_DAYS} days', 'YYYY-MM-DD')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM account_nudges an
                  WHERE an.user_id = u.id AND an.nudge_type = 'log_reminder'
              )
            ON CONFLICT (user_id, nudge_type) DO NOTHING
            RETURNING id
        ''',
        'delete': f'''
            DELETE FROM account_nudges an
            WHERE an.nudge_type = 'log_reminder'
              AND (
                EXISTS (
                  SELECT 1 FROM training_log tl WHERE tl.user_id = an.user_id
                    AND tl.date >= TO_CHAR(NOW() - INTERVAL '{LOG_STALE_DAYS} days', 'YYYY-MM-DD')
                )
                OR EXISTS (
                  SELECT 1 FROM cardio_log cl WHERE cl.user_id = an.user_id
                    AND cl.date >= TO_CHAR(NOW() - INTERVAL '{LOG_STALE_DAYS} days', 'YYYY-MM-DD')
                )
              )
            RETURNING id
        ''',
    },
    {
        'nudge_type': 'body_metric_stale',
        # Only athletes who have EVER logged a body metric — this is a
        # "refresh", not a "start tracking" nudge — and not in the last window.
        'insert': f'''
            INSERT INTO account_nudges (user_id, nudge_type)
            SELECT u.id, 'body_metric_stale'
            FROM users u
            WHERE (u.created_at IS NULL
                   OR u.created_at <= NOW() - INTERVAL '{BODY_MIN_ACCOUNT_DAYS} days')
              AND EXISTS (
                  SELECT 1 FROM body_metrics bm WHERE bm.user_id = u.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM body_metrics bm WHERE bm.user_id = u.id
                    AND bm.date >= TO_CHAR(NOW() - INTERVAL '{BODY_STALE_DAYS} days', 'YYYY-MM-DD')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM account_nudges an
                  WHERE an.user_id = u.id AND an.nudge_type = 'body_metric_stale'
              )
            ON CONFLICT (user_id, nudge_type) DO NOTHING
            RETURNING id
        ''',
        'delete': f'''
            DELETE FROM account_nudges an
            WHERE an.nudge_type = 'body_metric_stale'
              AND EXISTS (
                  SELECT 1 FROM body_metrics bm WHERE bm.user_id = an.user_id
                    AND bm.date >= TO_CHAR(NOW() - INTERVAL '{BODY_STALE_DAYS} days', 'YYYY-MM-DD')
              )
            RETURNING id
        ''',
    },
    {
        'nudge_type': 'injury_review',
        # An injury still flagged 'Active' whose start_date is older than the
        # review window. Clears when the athlete resolves it (status changes)
        # or removes it.
        'insert': f'''
            INSERT INTO account_nudges (user_id, nudge_type)
            SELECT DISTINCT il.user_id, 'injury_review'
            FROM injury_log il
            WHERE il.status = 'Active'
              AND il.start_date <= TO_CHAR(NOW() - INTERVAL '{INJURY_REVIEW_DAYS} days', 'YYYY-MM-DD')
              AND NOT EXISTS (
                  SELECT 1 FROM account_nudges an
                  WHERE an.user_id = il.user_id AND an.nudge_type = 'injury_review'
              )
            ON CONFLICT (user_id, nudge_type) DO NOTHING
            RETURNING id
        ''',
        'delete': f'''
            DELETE FROM account_nudges an
            WHERE an.nudge_type = 'injury_review'
              AND NOT EXISTS (
                  SELECT 1 FROM injury_log il WHERE il.user_id = an.user_id
                    AND il.status = 'Active'
                    AND il.start_date <= TO_CHAR(NOW() - INTERVAL '{INJURY_REVIEW_DAYS} days', 'YYYY-MM-DD')
              )
            RETURNING id
        ''',
    },
    {
        'nudge_type': 'plan_needs_review',
        # A live (non-superseded, non-archived) plan version parked at the Layer
        # 3D review gate for at least the grace window. Archived plans are
        # excluded — the athlete deliberately shelved those. The grace window
        # keys off `created_at` (generation parks at the gate shortly after
        # start, so it's a close proxy for "parked at"); it gives the athlete a
        # few days to resolve the gate before being reminded.
        'insert': f'''
            INSERT INTO account_nudges (user_id, nudge_type)
            SELECT DISTINCT pv.user_id, 'plan_needs_review'
            FROM plan_versions pv
            WHERE pv.generation_status = 'needs_review'
              AND pv.superseded_at IS NULL
              AND pv.archived_at IS NULL
              AND pv.created_at <= NOW() - INTERVAL '{PLAN_REVIEW_STALE_DAYS} days'
              AND NOT EXISTS (
                  SELECT 1 FROM account_nudges an
                  WHERE an.user_id = pv.user_id AND an.nudge_type = 'plan_needs_review'
              )
            ON CONFLICT (user_id, nudge_type) DO NOTHING
            RETURNING id
        ''',
        # Clears once no live plan remains at the gate — the athlete resolved it
        # (status flips off 'needs_review'), superseded it, archived it, or
        # deleted it. The grace-window clause is intentionally omitted: it only
        # ever becomes *more* true with age, so it plays no part in clearing.
        'delete': '''
            DELETE FROM account_nudges an
            WHERE an.nudge_type = 'plan_needs_review'
              AND NOT EXISTS (
                  SELECT 1 FROM plan_versions pv WHERE pv.user_id = an.user_id
                    AND pv.generation_status = 'needs_review'
                    AND pv.superseded_at IS NULL
                    AND pv.archived_at IS NULL
              )
            RETURNING id
        ''',
    },
]


@bp.route('/cron/nudges/reconcile', methods=['GET'])
def scan_reconcile_staleness():
    """Daily reconcile for the #964 reminder / staleness nudges.

    For each staleness type, in one pass:
      1. **DELETE** rows whose condition has lifted (athlete logged, refreshed,
         or resolved). Removing the row — dismissed or not — lets the same
         nudge fire fresh on a future recurrence; the `UNIQUE (user_id,
         nudge_type)` constraint would otherwise block re-insertion forever.
      2. **INSERT** one row per newly-eligible athlete (condition holds, no
         existing row). `ON CONFLICT DO NOTHING` makes overlapping cron fires
         idempotent.

    Display still honours per-type in-app preferences at read time
    (`get_active_nudges`), so this stays preference-agnostic — toggling a type
    off mutes it without disturbing the reconciled rows.

    Token-gated like the other cron drains. Returns JSON
    `{inserted: {type: n, ...}, cleared: {type: n, ...}}`.
    """
    if not cron_authorized():
        abort(401)
    db = get_db()
    inserted: dict[str, int] = {}
    cleared: dict[str, int] = {}
    for spec in _STALENESS_RECONCILE:
        t = spec['nudge_type']
        cleared[t] = len(db.execute(spec['delete']).fetchall())
        inserted[t] = len(db.execute(spec['insert']).fetchall())
    db.commit()
    return jsonify(inserted=inserted, cleared=cleared), 200


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
