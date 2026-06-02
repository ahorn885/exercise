"""Render smoke tests for the redesign §21 Notifications feed.

Boots the real Flask app with a fake DB and drives `nudges.feed`
(`GET /notifications`) through `render_template` on the new shell.
`get_feed_nudges` makes two reads — undismissed ('New', keyed by
`dismissed_at IS NULL`) and dismissed ('Earlier', `IS NOT NULL`) — plus
the user-hydration fetchone and the context-processor's `active_nudges`
read (which reuses the undismissed query). A fake connection routes each
SELECT by SQL fragment. Assertions stay structural + CSP-clean.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        # User-hydration query path (and any stray fetchone). The nudge
        # reads all use fetchall(), so this only feeds _require_login.
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _Conn:
    """Routes the two nudge SELECTs by SQL fragment. The dismissed read
    carries `dismissed_at IS NOT NULL`; the undismissed read (used by both
    the feed's 'New' list and the active_nudges context processor) carries
    `dismissed_at IS NULL`. Everything else gets an empty cursor."""

    def __init__(self, new_rows, dismissed_rows):
        self._new = new_rows
        self._dismissed = dismissed_rows

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'account_nudges' in s and 'IS NOT NULL' in s:
            return _Cursor(self._dismissed)
        if 'account_nudges' in s and 'dismissed_at IS NULL' in s:
            return _Cursor(self._new)
        return _Cursor([])

    def commit(self):
        pass


def _row(**kw):
    base = {'id': 1, 'nudge_type': 'connect_provider_14d',
            'created_at': None, 'dismissed_at': None}
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, new_rows, dismissed_rows):
    conn = _Conn(new_rows, dismissed_rows)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_feed_renders_new_and_earlier(monkeypatch):
    # 'New' uses connect_provider_14d (display_delay 0 → always surfaces);
    # 'Earlier' uses target_race_skipped to exercise a second registry entry.
    new = [_row(id=1, nudge_type='connect_provider_14d')]
    dismissed = [_row(id=2, nudge_type='target_race_skipped',
                      dismissed_at='2026-05-20')]
    client = _client(monkeypatch, new, dismissed)
    resp = client.get('/notifications')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'What needs your attention.' in html
    # New nudge: registry message + CTA label + an inline dismiss form.
    assert 'fitness provider connected' in html
    assert 'Connect a provider' in html
    assert '/nudges/1/dismiss' in html
    # Earlier (dismissed) section: its message shows, but no dismiss form.
    assert 'Earlier' in html
    assert 'skipped picking a target race' in html
    assert '/nudges/2/dismiss' not in html
    # CSP-clean.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_feed_empty_all_caught_up(monkeypatch):
    client = _client(monkeypatch, [], [])
    resp = client.get('/notifications')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'All caught up' in html
    # No dismissed rows → the Earlier section block is absent (the phrase
    # "Earlier" still appears in the intro copy, so key off the class).
    assert 'nf-earlier' not in html
    assert 'style="' not in html


def test_settings_renders_readonly(monkeypatch):
    # §22 doesn't read account_nudges (it's registry-derived) — empty
    # context-processor reads are enough to render.
    client = _client(monkeypatch, [], [])
    resp = client.get('/notifications/settings')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'How AIDSTATION reaches you.' in html
    # Both channels described; at least one live registry reminder shown.
    assert 'In-app' in html
    assert 'Email' in html
    assert 'fitness provider connected' in html
    # Honest no-toggle posture: no checkboxes/selects, CSP-clean.
    assert 'type="checkbox"' not in html
    assert '<select' not in html
    assert 'style="' not in html
