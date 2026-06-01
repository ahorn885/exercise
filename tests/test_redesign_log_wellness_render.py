"""Render smoke tests for the redesign §08 (Strength pane) and §09 (Wellness).

There's no local Postgres in CI and `database.get_db()` has no SQLite
fallback, so we boot the *real* Flask app (gate + blueprints + the
token-CSS shell templates all wired together) and swap `get_db` for a
fake connection that returns empty result sets. That's enough to drive
both routes through `render_template`, which is the integration these
tests guard: the new `training/session_form.html` extends the unified Log
shell (so the type picker renders around it), and `wellness/index.html`
extends the redesign `base.html` and carries the `#self-report` deep-link
target the Log picker's Wellness tile now points at.

The assertions stay structural (status 200, shell present, the specific
hooks each screen must expose) rather than pixel-level — parity with the
artboard is a manual/visual check per the build conventions.
"""

from __future__ import annotations

import os
import sys

# Must precede the `app` import — read at module-import time (mirrors
# tests/test_app_auth_gate.py). Empty DATABASE_URL makes the module-level
# init_postgres() fail fast (caught) instead of hanging on a real host.
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import pytest

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    """dict that also supports the sqlite3.Row-ish access the routes use."""


class _FakeCursor:
    def fetchone(self):
        # A truthy, attribute/`.get`-friendly row. Enough for current_user()
        # hydration and wellness' `today_row`.
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return []


class _FakeConn:
    def execute(self, *a, **k):
        return _FakeCursor()

    def commit(self):
        pass


def _fake_get_db():
    return _FakeConn()


@pytest.fixture()
def client(monkeypatch):
    # Every module that did `from database import get_db` holds its own
    # binding, so patch the name wherever it resolved.
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', _fake_get_db, raising=False)

    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_strength_pane_renders_in_log_shell(client):
    resp = client.get('/training/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Redesign shell + unified Log picker wrap the strength form.
    assert 'app-shell' in html
    assert 'log-picker' in html
    assert 'class="log-type active"' in html  # strength tile is the active one
    # The set-log + save machinery survived the migration.
    assert 'id="set-log-body"' in html
    assert 'id="save-btn"' in html
    # CSP hygiene: no inline style/handlers leaked into the rendered page.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_wellness_renders_on_redesign_shell(client):
    resp = client.get('/wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # The Log picker's Wellness tile deep-links to this anchor.
    assert 'id="self-report"' in html
    # Self-report form still posts every rating field.
    for name in ('sleep_hours', 'sleep_quality', 'energy', 'soreness', 'mood'):
        assert f'name="{name}"' in html
    assert 'style="' not in html


def test_log_picker_wellness_tile_targets_self_report_anchor(client):
    # The picker renders inside any log pane; the cardio default carries it.
    resp = client.get('/cardio/new')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '/wellness#self-report' in html
