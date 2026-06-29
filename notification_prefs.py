"""Notification delivery-preference registry (#963 / epic #259).

The single source of truth for **what** AIDSTATION can notify about
(`NOTIFICATION_TYPES`) and **how** it can reach you (`CHANNELS`), plus the
default per-(type × channel) opt-in matrix. Pure data + resolution helpers —
no DB, no Flask — so it imports cleanly into the repo layer, the settings
route, and the delivery sites (e.g. `plan_notifications.notify_plan_terminal`)
without dragging a request context along.

Design notes
------------
- **Channels.** `in_app` (the feed + dashboard badge) and `email` ship today;
  `push` is *wired but undeliverable* — there's no native app yet, so the
  preference is storable and editable now and delivery lands later (#963 scope:
  "wire the preference now, deliver later"). `channel_available()` is the gate
  delivery code checks so an enabled-but-unavailable channel never fires.
- **Applicability.** Not every type makes sense on every channel — account
  reminders are in-app-only. A type lists its applicable channels; cells
  outside that set are neither shown as toggles nor ever delivered.
- **Defaults vs overrides.** This module owns the *defaults*; per-user
  overrides live in `notification_preferences` (see
  `notification_preferences_repo`). `default_enabled()` is the fallback when a
  user has no stored override for a cell.

Adding a new trigger type (the sibling-issue work this is the foundation for)
means one entry in `NOTIFICATION_TYPES` and a delivery site that checks
`notification_preferences_repo.channel_enabled` — the settings matrix, the
defaults, and validation all follow automatically.
"""

from __future__ import annotations


# Delivery channels, in display order (settings-matrix column order).
#   key        — stored in `notification_preferences.channel`
#   label      — column header
#   available  — False ⇒ preference is editable/storable but never delivered
#                (push, gated on a native app — #963)
#   note       — short caption rendered under unavailable channels
CHANNELS = [
    {'key': 'in_app', 'label': 'In-app', 'available': True,
     'note': 'The notifications feed and dashboard badge.'},
    {'key': 'push', 'label': 'Push', 'available': False,
     'note': 'Arrives once the mobile app ships — set it now, it just '
             'won\'t deliver yet.'},
    {'key': 'email', 'label': 'Email', 'available': True,
     'note': 'Sent to the address on your account.'},
]

CHANNELS_BY_KEY = {c['key']: c for c in CHANNELS}
CHANNEL_KEYS = [c['key'] for c in CHANNELS]


# Notification types, in display order (settings-matrix row order).
#   key          — stored in `notification_preferences.notification_type`
#   label        — row heading
#   description  — one line of plain-terms copy
#   category     — chip styling ('good' / 'warning' / 'info')
#   channels     — applicable channel keys (a subset of CHANNEL_KEYS)
#   defaults     — per-channel default opt-in; missing ⇒ off
#
# `plan_ready` / `plan_failed` map to the live #260 plan-lifecycle path
# (`plan_notifications.py`). `science_update` is the #451 trigger this infra
# unblocks. `account_reminders` covers the in-app onboarding/connect nudges
# (`routes.nudges.NUDGE_REGISTRY`) — in-app only by nature.
NOTIFICATION_TYPES = [
    {
        'key': 'plan_ready',
        'label': 'Plan ready',
        'description': 'Your training plan finished generating and is ready '
                       'to view.',
        'category': 'good',
        'channels': ['in_app', 'push', 'email'],
        'defaults': {'in_app': True, 'push': True, 'email': True},
    },
    {
        'key': 'plan_failed',
        'label': "Plan couldn't be generated",
        'description': 'Plan generation hit an error and needs another try.',
        'category': 'warning',
        'channels': ['in_app', 'push', 'email'],
        'defaults': {'in_app': True, 'push': True, 'email': True},
    },
    {
        'key': 'science_update',
        'label': 'Science update affects your plan',
        'description': 'New evidence would materially change your plan and a '
                       'refresh is available.',
        'category': 'info',
        'channels': ['in_app', 'push', 'email'],
        # Email off by default — opt-in, not opt-out (avoids unsolicited
        # digest-style mail). In-app + push surface it passively.
        'defaults': {'in_app': True, 'push': True, 'email': False},
    },
    {
        'key': 'account_reminders',
        'label': 'Account reminders',
        'description': 'Nudges to connect a provider or finish onboarding '
                       'steps you skipped.',
        'category': 'info',
        # In-app only — these are passive banners, never emailed/pushed.
        'channels': ['in_app'],
        'defaults': {'in_app': True},
    },
    # ─── #964 reminder / staleness triggers ─────────────────────────────────
    # Surfaced as in-app `account_nudges` rows reconciled by the daily cron
    # (`routes.nudges.scan_reconcile_staleness`). Email is intentionally NOT an
    # applicable channel: there is no nudge→email delivery path yet, and
    # `email` is `available: True`, so listing it would render an enabled
    # toggle that silently never delivers. `push` follows the project-wide
    # "store the preference now, deliver once the app ships" posture.
    {
        'key': 'log_reminder',
        'label': 'Log your workouts',
        'description': "A nudge when you haven't logged a workout in a few "
                       'days, so your training record stays current.',
        'category': 'info',
        'channels': ['in_app', 'push'],
        'defaults': {'in_app': True, 'push': True},
    },
    {
        'key': 'body_metric_stale',
        'label': 'Refresh your body metrics',
        'description': "A reminder to update your weight / body metrics when "
                       "they haven't been refreshed in a while.",
        'category': 'info',
        'channels': ['in_app', 'push'],
        'defaults': {'in_app': True, 'push': True},
    },
    {
        'key': 'injury_review',
        'label': 'Review your injuries',
        'description': "A reminder to revisit an injury that's been marked "
                       'active for a while — resolve it or update its status.',
        'category': 'info',
        'channels': ['in_app', 'push'],
        'defaults': {'in_app': True, 'push': True},
    },
    # A plan parked at the Layer 3D review gate (`generation_status =
    # 'needs_review'`) can never finish until the athlete resolves it. Distinct
    # from `plan_failed` (a generation *error* event): this is a still-open plan
    # the athlete must act on. Reconciled by the same daily cron; `warning`
    # category since it blocks a plan from completing.
    {
        'key': 'plan_needs_review',
        'label': 'Plan needs your review',
        'description': "A reminder when a plan you started is waiting on you to "
                       'resolve its review items before it can finish.',
        'category': 'warning',
        'channels': ['in_app', 'push'],
        'defaults': {'in_app': True, 'push': True},
    },
]

TYPES_BY_KEY = {t['key']: t for t in NOTIFICATION_TYPES}
TYPE_KEYS = [t['key'] for t in NOTIFICATION_TYPES]


def is_valid_type(type_key: str) -> bool:
    """True iff `type_key` is a registered notification type."""
    return type_key in TYPES_BY_KEY


def is_valid_channel(channel_key: str) -> bool:
    """True iff `channel_key` is a registered delivery channel."""
    return channel_key in CHANNELS_BY_KEY


def is_applicable(type_key: str, channel_key: str) -> bool:
    """True iff this type can be delivered on this channel at all.

    Unknown type/channel pairs are non-applicable (False) rather than raising —
    callers (validation, the matrix builder, delivery gates) treat a bad pair as
    "no such toggle" uniformly.
    """
    t = TYPES_BY_KEY.get(type_key)
    return bool(t) and channel_key in t['channels']


def default_enabled(type_key: str, channel_key: str) -> bool:
    """The shipped default opt-in for a cell, ignoring user overrides.

    False for non-applicable pairs (there's nothing to deliver), and for
    applicable pairs absent from the type's `defaults` map.
    """
    if not is_applicable(type_key, channel_key):
        return False
    return bool(TYPES_BY_KEY[type_key]['defaults'].get(channel_key, False))


def channel_available(channel_key: str) -> bool:
    """True iff this channel can actually deliver today.

    `push` is registered + storable but returns False until the native app
    ships — delivery code must gate on this so an enabled-but-undeliverable
    channel is a silent no-op, not a crash or a dropped message elsewhere.
    """
    c = CHANNELS_BY_KEY.get(channel_key)
    return bool(c) and bool(c['available'])


# Plan-lifecycle `generation_status` → notification type. Mirrors the
# 'ready'/'failed' terminal statuses `plan_notifications` fires on; anything
# else has no notification type (returns None).
_PLAN_STATUS_TYPE = {'ready': 'plan_ready', 'failed': 'plan_failed'}


def type_for_plan_status(status: str | None) -> str | None:
    """Notification type for a plan terminal `generation_status`, or None.

    Lets the #260 delivery path translate the column it already has
    ('ready'/'failed') into the registry key the preference store is keyed on
    without hard-coding the mapping at the call site.
    """
    return _PLAN_STATUS_TYPE.get(status or '')
