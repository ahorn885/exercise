"""Per-user recurring-send schedule store (#964).

The *when* for the recurring time-of-day notification family — supplement AM/PM
reminders, the next-day-workouts preview, and the opt-in daily log ping. Sits
beside `notification_preferences` (the *whether* matrix): a preference says a
type may reach you in-app; a schedule says at what local hour the recurring send
fires. The hourly cron (`routes.nudges.scan_scheduled_sends`, Slice 2) localizes
`send_hour` against `users.timezone` and fires a feed nudge once per local day.

Table (PG-only, in `_PG_MIGRATIONS`):

    notification_schedules (
        user_id, schedule_type, send_hour, enabled, last_sent_on, updated_at,
        PRIMARY KEY (user_id, schedule_type)
    )
    users.timezone TEXT   -- IANA name; NULL ⇒ schedules never fire

`schedule_type` is the same string as the `account_nudges.nudge_type` the cron
fires (and the `notification_type` it rolls up to for the in-app preference gate
is declared per entry). Reads on the settings page fail **open** to the shipped
defaults (SQLite dev has no such table) so the page always renders.
"""

from __future__ import annotations


# Recurring-send schedule types, in display order (settings-page row order).
#   key                — stored in `notification_schedules.schedule_type` AND
#                        the `account_nudges.nudge_type` the cron fires (identity)
#   label / description — settings-page copy
#   notification_type  — the `notification_prefs` key this rolls up to for the
#                        §22 in-app delivery gate (AM + PM share one toggle)
#   default_hour       — pre-checked local hour when the user has no row yet
SCHEDULE_TYPES = [
    {
        'key': 'supplement_am',
        'label': 'Morning supplements',
        'description': 'A daily reminder to take your morning supplements.',
        'notification_type': 'supplement_reminder',
        'default_hour': 7,
    },
    {
        'key': 'supplement_pm',
        'label': 'Evening supplements',
        'description': 'A daily reminder to take your evening supplements.',
        'notification_type': 'supplement_reminder',
        'default_hour': 20,
    },
    {
        'key': 'next_day_workouts',
        'label': "Tomorrow's training",
        'description': "An evening preview of tomorrow's sessions.",
        'notification_type': 'next_day_workouts',
        'default_hour': 19,
    },
    {
        'key': 'daily_log_ping',
        'label': 'Daily log reminder',
        'description': 'A once-a-day nudge to log your training.',
        'notification_type': 'daily_log_ping',
        'default_hour': 21,
    },
]

SCHEDULE_TYPES_BY_KEY = {s['key'] for s in SCHEDULE_TYPES}

# Hour options for the picker: (value, label) for 0–23 in local time.
HOUR_CHOICES = [
    (h, f"{(h % 12) or 12}:00 {'AM' if h < 12 else 'PM'}") for h in range(24)
]

# Curated IANA timezones for the picker (the common North-American zones plus a
# handful of international ones). Not the full tz database — a short, sensible
# list keeps the no-JS dropdown usable; expand if athletes outside these land.
TIMEZONES = [
    'America/New_York', 'America/Chicago', 'America/Denver', 'America/Phoenix',
    'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu',
    'America/Toronto', 'America/Vancouver', 'America/Mexico_City',
    'America/Sao_Paulo', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
    'Europe/Athens', 'Africa/Johannesburg', 'Asia/Dubai', 'Asia/Kolkata',
    'Asia/Singapore', 'Asia/Tokyo', 'Australia/Sydney', 'Pacific/Auckland',
    'UTC',
]
_TIMEZONES_SET = set(TIMEZONES)


def is_valid_schedule_type(key: str) -> bool:
    """True iff `key` is a registered recurring-send schedule type."""
    return key in SCHEDULE_TYPES_BY_KEY


def _valid_hour(value) -> int | None:
    """Parse a submitted hour to an int in 0–23, or None if malformed/out of
    range — a crafted POST can't store a nonsense send hour."""
    try:
        h = int(value)
    except (TypeError, ValueError):
        return None
    return h if 0 <= h <= 23 else None


def get_schedules(db, user_id: int) -> dict[str, dict]:
    """Every stored schedule for `user_id`, keyed `schedule_type -> {send_hour,
    enabled}`. Empty for a falsy user (no query). Raises if the table is absent
    (SQLite dev) — `build_schedule_view` wraps this and degrades to defaults."""
    if not user_id:
        return {}
    rows = db.execute(
        'SELECT schedule_type, send_hour, enabled '
        'FROM notification_schedules WHERE user_id = ?',
        (user_id,),
    ).fetchall()
    return {r['schedule_type']: {'send_hour': r['send_hour'],
                                 'enabled': bool(r['enabled'])}
            for r in rows}


def get_user_timezone(db, user_id: int) -> str | None:
    """The user's stored IANA timezone, or None if unset / unreadable. Fails
    open to None (the "not configured yet" state) so the page renders."""
    if not user_id:
        return None
    try:
        row = db.execute(
            'SELECT timezone FROM users WHERE id = ?', (user_id,),
        ).fetchone()
    except Exception as e:  # noqa: BLE001 — treat as unset, never 500
        print(f'notification_schedules_repo: timezone read failed: {e}')
        return None
    return row['timezone'] if row else None


def build_schedule_view(db, user_id: int) -> dict:
    """The settings-page view model: the current timezone plus one row per
    schedule type carrying its resolved `send_hour` + `enabled`.

    A type with no stored row resolves to `enabled=False` at its `default_hour`
    (off until the athlete opts in, pre-positioned at a sensible hour). The
    override read fails open to defaults (SQLite dev) so the page always renders.
    """
    try:
        stored = get_schedules(db, user_id)
    except Exception as e:  # noqa: BLE001 — render defaults, never 500
        print(f'notification_schedules_repo: schedule read failed: {e}')
        stored = {}
    rows = []
    for s in SCHEDULE_TYPES:
        cur = stored.get(s['key'])
        rows.append({
            'key': s['key'],
            'label': s['label'],
            'description': s['description'],
            'notification_type': s['notification_type'],
            'send_hour': cur['send_hour'] if cur else s['default_hour'],
            'enabled': cur['enabled'] if cur else False,
            'hour_field': f"sched:{s['key']}:hour",
            'enabled_field': f"sched:{s['key']}:enabled",
        })
    return {
        'timezone': get_user_timezone(db, user_id),
        'rows': rows,
    }


def set_schedule(db, user_id: int, schedule_type: str, send_hour: int,
                 enabled: bool) -> bool:
    """Upsert one schedule row. No-ops (returns False) for a falsy user, an
    unknown schedule_type, or an out-of-range hour. Preserves `last_sent_on`
    (only the cron advances it). Caller commits."""
    if not user_id or not is_valid_schedule_type(schedule_type):
        return False
    h = _valid_hour(send_hour)
    if h is None:
        return False
    db.execute(
        'INSERT INTO notification_schedules '
        '(user_id, schedule_type, send_hour, enabled, updated_at) '
        'VALUES (?, ?, ?, ?, NOW()) '
        'ON CONFLICT (user_id, schedule_type) '
        'DO UPDATE SET send_hour = EXCLUDED.send_hour, '
        'enabled = EXCLUDED.enabled, updated_at = NOW()',
        (user_id, schedule_type, h, bool(enabled)),
    )
    return True


def set_user_timezone(db, user_id: int, timezone: str | None) -> bool:
    """Persist the user's IANA timezone. No-ops (returns False) for a falsy user
    or a value outside the curated `TIMEZONES` list — a crafted POST can't store
    an arbitrary string. Caller commits."""
    if not user_id or timezone not in _TIMEZONES_SET:
        return False
    db.execute('UPDATE users SET timezone = ? WHERE id = ?',
               (timezone, user_id))
    return True


def save_schedules_from_form(db, user_id: int, form) -> int:
    """Persist a full schedule submit from the settings form.

    Each type is written explicitly: the enable checkbox (`sched:<type>:enabled`)
    posts only when on, so the off state is captured by iterating the registry
    rather than the form; the hour comes from `sched:<type>:hour`. The timezone
    (`timezone`) is saved when it's a valid choice. One commit for the whole
    submit. Returns the number of schedule rows written (timezone excluded).
    """
    if not user_id:
        return 0
    written = 0
    for s in SCHEDULE_TYPES:
        hour = _valid_hour(form.get(f"sched:{s['key']}:hour"))
        if hour is None:
            hour = s['default_hour']
        enabled = f"sched:{s['key']}:enabled" in form
        if set_schedule(db, user_id, s['key'], hour, enabled):
            written += 1
    set_user_timezone(db, user_id, form.get('timezone'))
    db.commit()
    return written
