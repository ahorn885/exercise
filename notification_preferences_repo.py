"""Per-user notification-preference store (#963).

Thin DB layer over `notification_preferences` — the override table behind the
§22 settings matrix. The registry (`notification_prefs`) owns the *defaults*;
this module owns the *user-specific deviations from them*. A cell with no row
here resolves to its registry default, so a brand-new user has a fully sensible
matrix without any seeding.

Table (PG-only, in `_PG_MIGRATIONS`):

    notification_preferences (
        user_id, notification_type, channel, enabled, updated_at,
        PRIMARY KEY (user_id, notification_type, channel)
    )

Resolution is `override if present else registry default`. Reads are best-effort
at the call sites that run on hot/never-500 paths (the dashboard badge, the
plan-terminal delivery): SQLite dev has no such table, so every public function
that a non-settings caller depends on is written to fail-open to the default
behaviour (deliver / show) rather than suppress — a preference-store hiccup must
never silently swallow a notification.
"""

from __future__ import annotations

import notification_prefs as np


def get_overrides(db, user_id: int) -> dict[tuple[str, str], bool]:
    """Every stored override for `user_id`, keyed `(type, channel) -> enabled`.

    Empty for a falsy `user_id` (no query). Raises if the table is absent
    (SQLite dev) — callers that must not 500 wrap this; `build_matrix` already
    degrades to defaults on any read fault.
    """
    if not user_id:
        return {}
    rows = db.execute(
        'SELECT notification_type, channel, enabled '
        'FROM notification_preferences WHERE user_id = ?',
        (user_id,),
    ).fetchall()
    return {(r['notification_type'], r['channel']): bool(r['enabled'])
            for r in rows}


def resolve(type_key: str, channel_key: str,
            overrides: dict[tuple[str, str], bool]) -> bool:
    """Effective opt-in for one cell: the override if present, else the
    registry default. Non-applicable cells are always False."""
    if not np.is_applicable(type_key, channel_key):
        return False
    key = (type_key, channel_key)
    if key in overrides:
        return overrides[key]
    return np.default_enabled(type_key, channel_key)


def build_matrix(db, user_id: int) -> list[dict]:
    """The settings-page matrix: one row per notification type, each carrying a
    `cells` list aligned to `notification_prefs.CHANNELS` order.

    Each cell: `{channel, label, applicable, available, enabled, field}` where
    `field` is the form input name (`pref:<type>:<channel>`) and `enabled` is the
    resolved opt-in. Non-applicable cells render as an em-dash; unavailable
    channels (push) stay editable but are flagged so the template can note that
    delivery is pending.

    Best-effort on the override read — a fault (e.g. SQLite dev, where the table
    doesn't exist) degrades to the shipped defaults so the page always renders.
    """
    try:
        overrides = get_overrides(db, user_id)
    except Exception as e:  # noqa: BLE001 — render defaults, never 500
        print(f'notification_preferences_repo: override read failed: {e}')
        overrides = {}
    matrix = []
    for t in np.NOTIFICATION_TYPES:
        cells = []
        for c in np.CHANNELS:
            applicable = np.is_applicable(t['key'], c['key'])
            cells.append({
                'channel': c['key'],
                'label': c['label'],
                'applicable': applicable,
                'available': c['available'],
                'enabled': resolve(t['key'], c['key'], overrides),
                'field': f"pref:{t['key']}:{c['key']}",
            })
        matrix.append({
            'key': t['key'],
            'label': t['label'],
            'description': t['description'],
            'category': t['category'],
            'cells': cells,
        })
    return matrix


def set_pref(db, user_id: int, type_key: str, channel_key: str,
             enabled: bool) -> bool:
    """Upsert one preference cell. No-ops (returns False) for a falsy user or a
    non-applicable `(type, channel)` pair — a crafted POST for a cell that isn't
    a real toggle writes nothing. Caller commits."""
    if not user_id or not np.is_applicable(type_key, channel_key):
        return False
    db.execute(
        'INSERT INTO notification_preferences '
        '(user_id, notification_type, channel, enabled, updated_at) '
        'VALUES (?, ?, ?, ?, NOW()) '
        'ON CONFLICT (user_id, notification_type, channel) '
        'DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = NOW()',
        (user_id, type_key, channel_key, bool(enabled)),
    )
    return True


def save_from_form(db, user_id: int, form) -> int:
    """Persist a full matrix submit from the settings form.

    Every applicable cell is written explicitly from the presence of its
    checkbox (`pref:<type>:<channel>` in `form` ⇒ enabled, absent ⇒ disabled) —
    unchecked boxes don't post, so we iterate the registry rather than the form
    to capture the off state too. One commit for the whole submit. Returns the
    number of cells written.
    """
    if not user_id:
        return 0
    written = 0
    for t in np.NOTIFICATION_TYPES:
        for c in np.CHANNELS:
            if not np.is_applicable(t['key'], c['key']):
                continue
            field = f"pref:{t['key']}:{c['key']}"
            if set_pref(db, user_id, t['key'], c['key'], field in form):
                written += 1
    db.commit()
    return written


def channel_enabled(db, user_id: int, type_key: str, channel_key: str) -> bool:
    """Effective opt-in for one cell, read live — the delivery-time gate.

    Used by send sites (e.g. the #260 email path) to honour the user's choice.
    Fails **open** (returns the registry default) on any read fault so a
    preference-store outage never silently suppresses a real notification.
    Returns False for non-applicable pairs.
    """
    if not np.is_applicable(type_key, channel_key):
        return False
    default = np.default_enabled(type_key, channel_key)
    if not user_id:
        return default
    try:
        row = db.execute(
            'SELECT enabled FROM notification_preferences '
            'WHERE user_id = ? AND notification_type = ? AND channel = ?',
            (user_id, type_key, channel_key),
        ).fetchone()
    except Exception as e:  # noqa: BLE001 — fail open to the default
        print(f'notification_preferences_repo: channel read failed: {e}')
        return default
    if row is None:
        return default
    return bool(row['enabled'])


def disabled_in_app_types(db, user_id: int) -> set[str]:
    """Types the user has explicitly turned OFF for in-app delivery.

    Powers the dashboard-badge gate (`get_unseen_plan_notifications`): only an
    explicit opt-out suppresses the badge, so the default (no row) keeps showing
    it. One small indexed read; fails **closed to the empty set** (suppress
    nothing) on any fault so a store hiccup never hides notifications.
    """
    if not user_id:
        return set()
    try:
        rows = db.execute(
            'SELECT notification_type FROM notification_preferences '
            'WHERE user_id = ? AND channel = ? AND enabled = FALSE',
            (user_id, 'in_app'),
        ).fetchall()
    except Exception as e:  # noqa: BLE001 — suppress nothing on a read fault
        print(f'notification_preferences_repo: in_app gate read failed: {e}')
        return set()
    return {r['notification_type'] for r in rows}
