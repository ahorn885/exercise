"""Redesign §17 — Connections hub.

Consolidates four formerly-separate surfaces into one tabbed page:
  - the old `garmin.dashboard` (recent activity + auth status),
  - the standalone `garmin.debug_fit` FIT inspector,
  - the Wellness/`.FIT` import entry points, and
  - the Profile › Connections tab (provider connect/disconnect).

Three tabs, server-rendered via `?tab=` (no SPA — CSP-clean):
  - **Sources**  — OAuth providers (real `provider_auth` status via
    `load_connections`), Garmin shown PAUSED (CONVENTIONS §E.3), the
    webhook-only stub providers as "not available yet", and the `.FIT`
    drop zone (posts to the real `garmin.import_fit` pipeline).
  - **Files**    — recent imported activities (`cardio_log`, real) tagged
    manual-vs-synced by the `fit:` dedup-id scheme, plus the `.FIT` drop
    zone for actual imports. The developer-facing field-dump inspector is
    operator tooling and lives on the admin surface (`admin.fit_inspect`,
    issue #473), not here.
  - **Preferences** — a grounded, read-only explainer of how ingestion
    actually behaves today (content-hash dedup, sport sniffing, Garmin
    paused). The artboard's configurable trust-order / pull-window /
    retention controls have **no backend** and are intentionally not
    fabricated (same discipline as §10 priority / §12 A↔B compare).
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash)

from database import get_db
from routes.auth import current_user_id
from routes.profile import load_connections

bp = Blueprint('connections', __name__, url_prefix='/connections')

# Providers whose OAuth start endpoint isn't wired yet (webhook stubs). Shown
# as "not available yet" rather than a dead CONNECT button (grounding: don't
# offer an action with no route behind it).
STUB_PROVIDERS = (
    {'slug': 'zwift', 'label': 'Zwift', 'scopes': 'indoor activities'},
)

VALID_TABS = ('sources', 'files')

_ACTIVITY_SQL = (
    'SELECT id, date, activity, activity_name, duration_min, distance_mi, '
    'avg_hr, max_hr, calories, garmin_activity_id, created_at '
    'FROM cardio_log WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 25'
)

# Strength sessions don't live in cardio_log — they're one training_sessions
# row fanned out into per-exercise training_log rows (see garmin._bulk_insert_
# strength). Roll each session back up so the Files list shows it as a single
# activity, shaped like a cardio_log row so the template renders it uniformly.
# MIN(garmin_activity_id) carries the 'fit:' dedup prefix that drives the
# Manual-vs-Synced chip; the exercises of one session share a single gid.
_STRENGTH_SQL = (
    'SELECT ts.id AS id, ts.date AS date, '
    'MIN(tl.garmin_activity_id) AS garmin_activity_id, '
    'COUNT(tl.id) AS exercise_count, ts.created_at AS created_at '
    'FROM training_sessions ts JOIN training_log tl ON tl.session_id = ts.id '
    'WHERE ts.user_id = ? '
    'GROUP BY ts.id, ts.date, ts.created_at '
    'ORDER BY ts.date DESC, ts.id DESC LIMIT 25'
)


def _strength_row(s):
    """Shape a rolled-up strength session as a cardio_log-style row dict so the
    Files template can render strength and cardio in one list."""
    n = s['exercise_count']
    return {
        'id': s['id'],
        'date': s['date'],
        'activity': 'Strength',
        'activity_name': 'Strength session · %d exercise%s' % (
            n, '' if n == 1 else 's'),
        'duration_min': None,
        'distance_mi': None,
        'avg_hr': None,
        'max_hr': None,
        'calories': None,
        'garmin_activity_id': s['garmin_activity_id'],
        'created_at': s['created_at'],
    }


def _hub_context(db, uid, tab, **extra):
    """Shared render context for both the GET hub and the POST inspector."""
    oauth_providers = load_connections(
        db, uid, return_to=url_for('connections.hub'))
    garmin_auth = {'authenticated': False, 'username': None}
    try:
        from garmin_connect import get_auth_status
        garmin_auth = get_auth_status(db)
    except Exception:
        pass
    recent_activities = []
    activity_count = 0
    if tab == 'files':
        cardio = db.execute(_ACTIVITY_SQL, (uid,)).fetchall()
        strength = [_strength_row(s)
                    for s in db.execute(_STRENGTH_SQL, (uid,)).fetchall()]
        # Merge both sources newest-first and cap at the same 25-row window.
        recent_activities = sorted(
            list(cardio) + strength,
            key=lambda r: (r['date'], r['created_at']), reverse=True,
        )[:25]
        cardio_n = db.execute(
            'SELECT COUNT(*) AS n FROM cardio_log WHERE user_id = ?', (uid,)
        ).fetchone()
        strength_n = db.execute(
            'SELECT COUNT(*) AS n FROM training_sessions ts '
            'WHERE ts.user_id = ? AND EXISTS '
            '(SELECT 1 FROM training_log tl WHERE tl.session_id = ts.id)',
            (uid,)
        ).fetchone()
        activity_count = ((cardio_n['n'] if cardio_n else 0) or 0) \
            + ((strength_n['n'] if strength_n else 0) or 0)
    # Surface the OAuth round-trip outcome the provider callbacks append to the
    # return_to URL (`?<slug>_connected=1` / `?<slug>_oauth_error=…`). Mirrors
    # the onboarding Step-2 connect screen; without it a failed Wahoo/Strava/…
    # handshake bounced the athlete back here to a hub that looked unchanged,
    # giving no signal the attempt failed.
    just_connected_label = None
    oauth_error_label = None
    for p in oauth_providers:
        slug = p['slug']
        if just_connected_label is None and request.args.get(f'{slug}_connected') == '1':
            just_connected_label = p['label']
        if oauth_error_label is None and request.args.get(f'{slug}_oauth_error'):
            oauth_error_label = p['label']
    ctx = dict(
        tab=tab,
        oauth_providers=oauth_providers,
        stub_providers=STUB_PROVIDERS,
        garmin_auth=garmin_auth,
        connected_count=sum(1 for p in oauth_providers if p['is_connected']),
        # +1 for the Garmin (paused) row.
        provider_total=len(oauth_providers) + len(STUB_PROVIDERS) + 1,
        recent_activities=recent_activities,
        activity_count=activity_count,
        just_connected_label=just_connected_label,
        oauth_error_label=oauth_error_label,
    )
    ctx.update(extra)
    return ctx


@bp.route('/')
def hub():
    db = get_db()
    uid = current_user_id()
    tab = request.args.get('tab', 'sources')
    if tab not in VALID_TABS:
        tab = 'sources'
    return render_template('connections/hub.html', **_hub_context(db, uid, tab))
