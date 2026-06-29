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
from layer4.cache import Layer4Cache
from layer4.cache_postgres import PostgresCacheBackend
from routes.auth import current_user_id
from routes.profile import load_connections
from source_preference_apply import (
    apply_cardio_pin_change, apply_wellness_pin_change)
from source_preferences_repo import (
    CARDIO, VALID_PROVIDERS, WELLNESS, SourcePreferenceError,
    clear_source_preference, get_source_preferences, set_source_preference)

bp = Blueprint('connections', __name__, url_prefix='/connections')

# Display label per provider for the source-precedence picker (#196 P5 B4). The
# option VALUES are the provider names validated by `set_source_preference`
# against `VALID_PROVIDERS`; these are presentation-only.
_SOURCE_PRECEDENCE_LABELS = {
    'garmin': 'Garmin', 'whoop': 'Whoop', 'oura': 'Oura', 'polar': 'Polar',
    'coros': 'COROS', 'wahoo': 'Wahoo', 'rwgps': 'Ride With GPS',
    'strava': 'Strava',
}

# Providers whose OAuth start endpoint isn't wired yet (webhook stubs). Shown
# as "not available yet" rather than a dead CONNECT button (grounding: don't
# offer an action with no route behind it).
STUB_PROVIDERS = (
    {'slug': 'zwift', 'label': 'Zwift', 'scopes': 'indoor activities'},
)

VALID_TABS = ('sources', 'files')

# Reads canonical_cardio_feed (#196 Slice 4b), not raw cardio_log: a ride synced
# from N providers collapses to one best-of row in the Files list instead of N
# near-duplicates; unclustered/legacy rows still surface via the feed's
# NULL-cluster_id branch. (The literal cardio-LOG/edit pages stay on raw
# cardio_log — decision 2 — so a stray copy stays visible and deletable.)
_ACTIVITY_SQL = (
    'SELECT id, date, activity, activity_name, duration_min, distance_mi, '
    'avg_hr, max_hr, calories, garmin_activity_id, created_at '
    'FROM canonical_cardio_feed WHERE user_id = ? '
    'ORDER BY date DESC, id DESC LIMIT 25'
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


def _precedence_options(domain, current):
    """Dropdown options for a source-precedence domain (#196 P5 B4): the
    'Automatic' default (no pin) first, then every provider valid for the domain
    (sorted, deterministic), with the athlete's current pin marked selected."""
    opts = [{'value': '', 'label': 'Automatic (most complete)',
             'selected': not current}]
    for p in sorted(VALID_PROVIDERS[domain]):
        opts.append({'value': p,
                     'label': _SOURCE_PRECEDENCE_LABELS.get(p, p.title()),
                     'selected': p == current})
    return opts


def _precedence_flash(changed):
    """Coaching-voice confirmation for the saved pins — one clause per domain
    that actually changed."""
    parts = []
    for domain, choice in changed:
        dom = 'Wellness' if domain == WELLNESS else 'Activity'
        if choice:
            parts.append(
                f"{dom} source set to "
                f"{_SOURCE_PRECEDENCE_LABELS.get(choice, choice.title())}")
        else:
            parts.append(f"{dom} source back to automatic")
    return "; ".join(parts) + "."


def _hub_context(db, uid, tab, **extra):
    """Shared render context for both the GET hub and the POST inspector."""
    oauth_providers = load_connections(
        db, uid, return_to=url_for('connections.hub'))
    source_pins = get_source_preferences(db, uid)
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
            # canonical_cardio_feed (#196 Slice 4b): count each ride once.
            'SELECT COUNT(*) AS n FROM canonical_cardio_feed WHERE user_id = ?',
            (uid,)
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
        source_precedence={
            'wellness': _precedence_options(WELLNESS, source_pins.get(WELLNESS)),
            'cardio': _precedence_options(CARDIO, source_pins.get(CARDIO)),
        },
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


@bp.route('/source-precedence', methods=['POST'])
def source_precedence():
    """Save the athlete's preferred-source pins (#196 P5 B4 — Track B picker).

    One dropdown per domain (wellness / cardio); '' = Automatic (clear the pin).
    For each domain that actually changed, set/clear the pin then re-derive the
    affected canonical layer + evict the Layer-3A-dependent caches via the B2/B3
    apply helpers (`apply_wellness_pin_change` / `apply_cardio_pin_change`).
    Commits only when something changed; the apply helpers run in this request's
    transaction so the new pin and the re-materialized rows land together."""
    db = get_db()
    uid = current_user_id()
    current = get_source_preferences(db, uid)
    cache = Layer4Cache(PostgresCacheBackend(lambda: db))
    changed = []
    try:
        for domain, apply_fn in ((WELLNESS, apply_wellness_pin_change),
                                 (CARDIO, apply_cardio_pin_change)):
            choice = (request.form.get(f'pin_{domain}') or '').strip()
            if choice == (current.get(domain) or ''):
                continue  # unchanged — no re-materialize, no evict
            if choice:
                set_source_preference(db, uid, domain, choice)
            else:
                clear_source_preference(db, uid, domain)
            apply_fn(db, cache, uid)
            changed.append((domain, choice))
    except SourcePreferenceError as e:
        # Defensive: the dropdown only offers valid providers, so a violation
        # means a hand-crafted POST. Nothing is committed → the partial write is
        # discarded when the request connection closes uncommitted.
        flash(str(e), 'danger')
        return redirect(url_for('connections.hub', tab='sources'))
    if changed:
        db.commit()
        flash(_precedence_flash(changed), 'info')
    return redirect(url_for('connections.hub', tab='sources'))
