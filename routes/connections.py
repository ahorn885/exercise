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
    manual-vs-synced by the `fit:` dedup-id scheme, plus the inline `.FIT`
    inspector (reuses `garmin_fit_parser._dump_fit`, replacing debug_fit).
  - **Preferences** — a grounded, read-only explainer of how ingestion
    actually behaves today (content-hash dedup, sport sniffing, Garmin
    paused). The artboard's configurable trust-order / pull-window /
    retention controls have **no backend** and are intentionally not
    fabricated (same discipline as §10 priority / §12 A↔B compare).
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session as flask_session)
from werkzeug.utils import secure_filename

from database import get_db
from routes.auth import current_user_id
from routes.profile import load_connections

bp = Blueprint('connections', __name__, url_prefix='/connections')

# Providers whose OAuth start endpoint isn't wired yet (webhook stubs). Shown
# as "not available yet" rather than a dead CONNECT button (grounding: don't
# offer an action with no route behind it).
STUB_PROVIDERS = (
    {'slug': 'strava', 'label': 'Strava', 'scopes': 'activity · wellness'},
    {'slug': 'whoop', 'label': 'Whoop', 'scopes': 'workouts · sleep · recovery'},
    {'slug': 'trainingpeaks', 'label': 'TrainingPeaks', 'scopes': 'workouts · planned'},
    {'slug': 'zwift', 'label': 'Zwift', 'scopes': 'indoor activities'},
    {'slug': 'ride_with_gps', 'label': 'Ride With GPS', 'scopes': 'routes'},
)

VALID_TABS = ('sources', 'files', 'prefs')

_ACTIVITY_SQL = (
    'SELECT id, date, activity, activity_name, duration_min, distance_mi, '
    'avg_hr, max_hr, calories, garmin_activity_id, created_at '
    'FROM cardio_log WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 25'
)


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
        recent_activities = db.execute(_ACTIVITY_SQL, (uid,)).fetchall()
        row = db.execute(
            'SELECT COUNT(*) AS n FROM cardio_log WHERE user_id = ?', (uid,)
        ).fetchone()
        activity_count = (row['n'] if row else 0) or 0
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
        inspect_dumps=None,
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


@bp.route('/inspect', methods=['POST'])
def inspect():
    """Inline .FIT inspector for the Files tab — parses an uploaded .FIT (or
    every .fit inside a .zip) and renders the field dump alongside the file
    history. Replaces the standalone garmin.debug_fit surface."""
    db = get_db()
    uid = current_user_id()
    f = request.files.get('fit_file')
    if not f or not f.filename:
        flash('No file selected.', 'warning')
        return redirect(url_for('connections.hub', tab='files'))
    dumps = []
    try:
        from garmin_fit_parser import _dump_fit
        raw = f.read()
        fname = secure_filename(f.filename or '').lower()
        if fname.endswith('.zip'):
            import zipfile
            import io
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                fit_names = [n for n in zf.namelist()
                             if n.lower().endswith('.fit')]
                if not fit_names:
                    flash('No .fit file found inside the zip.', 'danger')
                    return redirect(url_for('connections.hub', tab='files'))
                for n in fit_names[:60]:
                    try:
                        dumps.append({'name': n, 'dump': _dump_fit(zf.read(n))})
                    except Exception as e:  # noqa: BLE001 — per-entry isolation
                        dumps.append({'name': n, 'error': str(e)})
        else:
            dumps.append({'name': f.filename, 'dump': _dump_fit(raw)})
    except Exception as e:  # noqa: BLE001 — surface parse errors to the user
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('connections.hub', tab='files'))
    # Drop any stale import payload so we never echo it back here.
    flask_session.pop('fit_inspect', None)
    return render_template(
        'connections/hub.html',
        **_hub_context(db, uid, 'files', inspect_dumps=dumps))
