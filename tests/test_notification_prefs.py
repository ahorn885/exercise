"""Tests for `notification_prefs.py` — the delivery-preference registry (#963).

Pure data + resolution; no DB, no Flask. Pins the invariants the repo, settings
route, and delivery gates all lean on: applicability, defaults, the push
availability gate, and the plan-status → type mapping.
"""

from __future__ import annotations

import notification_prefs as np


# ─── registry shape invariants ───────────────────────────────────────────────


def test_channels_include_in_app_push_email_in_order():
    assert [c['key'] for c in np.CHANNELS] == ['in_app', 'push', 'email']


def test_push_is_the_only_unavailable_channel():
    avail = {c['key']: c['available'] for c in np.CHANNELS}
    assert avail == {'in_app': True, 'push': False, 'email': True}


def test_every_type_defaults_only_reference_applicable_channels():
    # A default for a non-applicable channel would be dead config.
    for t in np.NOTIFICATION_TYPES:
        for ch in t['defaults']:
            assert ch in t['channels'], (t['key'], ch)


def test_every_type_channel_is_a_real_channel():
    for t in np.NOTIFICATION_TYPES:
        for ch in t['channels']:
            assert np.is_valid_channel(ch), (t['key'], ch)


def test_expected_types_registered():
    keys = set(np.TYPE_KEYS)
    assert {'plan_ready', 'plan_failed', 'science_update',
            'account_reminders'} <= keys


# ─── validation helpers ──────────────────────────────────────────────────────


def test_is_valid_type_and_channel():
    assert np.is_valid_type('plan_ready')
    assert not np.is_valid_type('nope')
    assert np.is_valid_channel('email')
    assert not np.is_valid_channel('sms')


def test_is_applicable():
    assert np.is_applicable('plan_ready', 'email')
    # account_reminders is in-app only.
    assert np.is_applicable('account_reminders', 'in_app')
    assert not np.is_applicable('account_reminders', 'email')
    assert not np.is_applicable('account_reminders', 'push')
    # Unknown pairs are non-applicable, never raise.
    assert not np.is_applicable('bogus', 'email')
    assert not np.is_applicable('plan_ready', 'sms')


# ─── defaults ────────────────────────────────────────────────────────────────


def test_default_enabled_known_cells():
    assert np.default_enabled('plan_ready', 'in_app') is True
    assert np.default_enabled('plan_ready', 'email') is True
    # science_update email is opt-in (off by default).
    assert np.default_enabled('science_update', 'email') is False
    assert np.default_enabled('science_update', 'in_app') is True


def test_default_enabled_false_for_non_applicable():
    assert np.default_enabled('account_reminders', 'email') is False
    assert np.default_enabled('bogus', 'in_app') is False


# ─── channel availability (the push gate) ────────────────────────────────────


def test_channel_available_gate():
    assert np.channel_available('in_app') is True
    assert np.channel_available('email') is True
    assert np.channel_available('push') is False
    assert np.channel_available('sms') is False


# ─── plan-status → type mapping ──────────────────────────────────────────────


def test_type_for_plan_status():
    assert np.type_for_plan_status('ready') == 'plan_ready'
    assert np.type_for_plan_status('failed') == 'plan_failed'
    assert np.type_for_plan_status('generating') is None
    assert np.type_for_plan_status(None) is None
