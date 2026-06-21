"""#814 — `/rx` display enrichment bridges layer0-renamed lifts by EX-id.

`exercise_inventory` is keyed on the v1 short names ('Back Squat'); plan-gen
prescribes the layer0 canonical names ('Back Squat (Barbell)'), so the old
`ei.exercise = cr.exercise` join missed for every renamed lift — its
discipline/type/video/where came back NULL and the lift double-listed in the
catalog under its v1 name. The fix indexes the catalog by the EX-id its v1 name
bridges to, so a layer0-named `current_rx` row (carrying that same EX-id) finds
its display row.

Boots the real Flask app with a fake DB (same harness as
test_redesign_rx_list_render) and asserts the render-level outcome: enrichment
shows, and the v1 catalog row no longer double-lists.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402
from exercise_inventory_bridge import (  # noqa: E402
    inventory_display_by_exid, v1_names_for_exid,
)


class _FakeRow(dict):
    pass


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, entries, inventory, locales):
        self._entries = entries
        self._inventory = inventory
        self._locales = locales

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM exercise_inventory' in s:
            return _Cursor(self._inventory)
        if 'FROM current_rx' in s:
            return _Cursor(self._entries)
        if 'FROM locale_profiles' in s:
            return _Cursor(self._locales)
        return _Cursor([])

    def commit(self):
        pass


def _entry(**kw):
    base = {
        'id': 1, 'exercise': 'Back squat', 'layer0_exercise_id': None,
        'discipline': 'Foot', 'type': 'Compound', 'movement_pattern': 'Squat',
        'current_sets': 3, 'current_reps': 5, 'current_weight': 225,
        'current_duration': None, 'last_performed': '2026-05-25',
        'last_outcome': '↑ progress', 'consecutive_failures': 0,
        'sessions_since_progress': 0, 'rx_source': 'From Training Log',
        'weight_increment': None, 'next_weight': None,
    }
    base.update(kw)
    return _FakeRow(base)


def _inv(**kw):
    base = {
        'exercise': 'Back Squat', 'discipline': 'Foot', 'type': 'Compound',
        'movement_pattern': 'Squat', 'suggested_volume': '5 × 5',
        'where_available': 'Home gym', 'recovery_cost': 'High',
        'video_reference': 'https://example.test/back-squat',
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, entries, inventory, locales):
    conn = _Conn(entries, inventory, locales)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


# ── Unit: the bridge maps inventory rows by the EX-id their v1 name resolves to ──

def test_inventory_display_by_exid_indexes_v1_name_to_exid():
    rows = [_inv(exercise='Back Squat'), _inv(exercise='Plank')]
    by_exid = inventory_display_by_exid(rows)
    assert by_exid['EX001']['exercise'] == 'Back Squat'   # Back Squat → EX001
    assert by_exid['EX216']['exercise'] == 'Plank'        # Plank → EX216


def test_inventory_display_by_exid_first_alias_wins_deterministically():
    # EX001 has >1 v1 alias ('Back Squat', 'Squat'); first row wins.
    rows = [_inv(exercise='Back Squat'), _inv(exercise='Squat')]
    by_exid = inventory_display_by_exid(rows)
    assert by_exid['EX001']['exercise'] == 'Back Squat'


def test_v1_names_for_exid_inverse_and_empty_on_miss():
    assert 'Back Squat' in v1_names_for_exid('EX001')
    assert v1_names_for_exid('EX_DOES_NOT_EXIST') == []
    assert v1_names_for_exid(None) == []


# NOTE: the two /rx render tests that exercised the bridge were removed when the
# catalog unification (Slice A) cut /rx + /exercises onto the single canonical
# layer0 catalog (EX-id keyed), retiring the name↔EX-id bridge on those paths.
# The render behavior is now covered by test_redesign_rx_list_render. The unit
# tests above stay: the bridge module is still consumed by coaching.py until the
# FK-child slice (Slice B) moves it onto layer0 EX-ids too.
