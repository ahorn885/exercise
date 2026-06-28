"""Render smoke tests for the redesign .FIT-import flow (finish-the-open).

Boots the real Flask app with a fake DB and drives the manual-upload path —
`garmin.import_fit`, `garmin.import_wellness`, `garmin.import_preview` —
through `render_template` on the new `.app` shell. The matcher + FIT parser
are stubbed so the route renders deterministically. Assertions stay
structural + CSP-clean (no inline style/handler; nonced scripts only).
"""

from __future__ import annotations

import io
import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402
import routes.garmin as _garmin  # noqa: E402


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
    def execute(self, sql, *a, **k):
        return _Cursor([])

    def commit(self):
        pass


def _client(monkeypatch):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _csp_clean(html):
    assert 'style="' not in html
    assert 'onclick=' not in html


# ── import.html (activity upload landing) ──────────────────────────────


def test_import_landing_on_shell(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/garmin/import')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Import .FIT files.' in html
    # Bulk uploader hooks (data-bulk-* → app.js) survive the migration.
    assert 'data-bulk-upload' in html
    assert 'data-bulk-drop' in html
    assert '/garmin/import/bulk' in html
    # Single-activity parse form + supported-types table.
    assert 'name="fit_file"' in html
    assert 'Parse file' in html
    assert 'Supported activity types' in html
    # Brand-neutral chrome — no top-level Garmin branding in the title.
    assert 'Import Garmin FIT' not in html
    _csp_clean(html)


# ── import_wellness.html (wellness upload + preview) ───────────────────


def test_wellness_landing_on_shell(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/garmin/import-wellness')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Import wellness .FIT.' in html
    assert 'data-bulk-upload' in html
    assert '/garmin/import-wellness/bulk' in html
    # preview=None → no sample table yet.
    assert 'Sample records' not in html
    _csp_clean(html)


def test_wellness_preview_relabels_recovery(monkeypatch):
    rows = [
        {'date': '2026-06-01', 'timestamp_ms': 1_717_200_000_000,
         'heart_rate': 58, 'stress_level': 22, 'body_battery': 76,
         'respiration_rate': 13, 'steps': 0, 'active_calories': 1},
        {'date': '2026-06-01', 'timestamp_ms': 1_717_200_060_000,
         'heart_rate': 60, 'stress_level': 25, 'body_battery': 74,
         'respiration_rate': 14, 'steps': 4, 'active_calories': 2},
    ]
    monkeypatch.setattr('garmin_fit_parser.parse_wellness_fit',
                        lambda raw: rows, raising=False)
    client = _client(monkeypatch)
    resp = client.post('/garmin/import-wellness',
                       data={'fit_file': (io.BytesIO(b'fake'), 'w.fit')},
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Sample records' in html
    assert 'Import 2 records' in html
    # CONVENTIONS §E.4 — "body battery" surfaces as "Recovery", no Garmin-ism.
    assert 'Recovery' in html
    assert 'Body battery' not in html
    assert 'Body Bat' not in html
    _csp_clean(html)


# ── import-wellness/bulk (zip extraction regression) ───────────────────


def test_wellness_bulk_extracts_every_fit_in_zip(monkeypatch):
    """Regression: import_wellness_bulk called `_iter_fit_blobs`, which #767
    Slice 2 (2026-06-19) renamed to `_iter_activity_blobs` — the wellness call
    site was missed, so every upload 500'd on a NameError and no wellness data
    landed. Assert the endpoint extracts each .fit inside a zip and routes it to
    ingest (would be a 500 before the fix)."""
    import zipfile
    monkeypatch.setattr('garmin_fit_parser.fit_file_meta',
                        lambda raw: ('metrics', 0), raising=False)
    calls = []

    def _fake_ingest(db, uid, name, raw, kind, results, summary):
        calls.append((name, kind))
        results.append({'name': name, 'status': 'imported', 'detail': kind})
        summary['files'] += 1
        summary['metrics_days'] += 1

    monkeypatch.setattr(_garmin, '_ingest_wellness_fit', _fake_ingest,
                        raising=False)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('2026-02-22_METRICS.fit', b'fake-metrics')
        zf.writestr('2026-02-22_SLEEP_DATA.fit', b'fake-sleep')
        zf.writestr('2026-02-22_WELLNESS.fit', b'fake-wellness')
    buf.seek(0)

    client = _client(monkeypatch)
    resp = client.post('/garmin/import-wellness/bulk',
                       data={'files': (buf, 'wellness.zip')},
                       content_type='multipart/form-data')
    assert resp.status_code == 200          # 500 (NameError) before the fix
    body = resp.get_json()
    assert body['ok'] is True
    # All three FITs inside the zip were extracted and routed to ingest.
    assert len(calls) == 3
    assert body['summary']['files'] == 3


def test_wellness_bulk_skips_non_fit_entries(monkeypatch):
    """The wellness-FIT endpoint skips a stray non-FIT upload (e.g. a .csv)
    rather than ingesting it — the `ext == 'fit'` gate added with the fix."""
    monkeypatch.setattr('garmin_fit_parser.fit_file_meta',
                        lambda raw: ('metrics', 0), raising=False)
    calls = []
    monkeypatch.setattr(_garmin, '_ingest_wellness_fit',
                        lambda *a: calls.append(a), raising=False)
    client = _client(monkeypatch)
    resp = client.post('/garmin/import-wellness/bulk',
                       data={'files': (io.BytesIO(b'a,b\n1,2\n'), 'whoop.csv')},
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()
    assert calls == []                       # csv not ingested by the wellness path
    assert body['summary']['skipped'] == 1


# ── import_preview.html (cardio + strength branches) ───────────────────


def _set_fit_import(client, parsed, name='', notes=''):
    with client.session_transaction() as sess:
        sess['fit_import'] = parsed
        sess['fit_name_override'] = name
        sess['fit_notes'] = notes


def test_preview_cardio_no_match(monkeypatch):
    monkeypatch.setattr(_garmin, 'find_best_match',
                        lambda db, a: None, raising=False)
    monkeypatch.setattr(_garmin, 'candidate_plan_items',
                        lambda db, d: [], raising=False)
    client = _client(monkeypatch)
    _set_fit_import(client, {
        'log_type': 'cardio',
        'data': {'activity': 'Trail Running', 'date': '2026-06-01',
                 'duration_min': 92, 'distance_mi': 8.4, 'avg_hr': 142},
    }, notes='felt strong')
    resp = client.get('/garmin/import/preview')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Preview import.' in html
    # No auto-match → the disposition radios + their nonced toggle script.
    assert 'class="disposition-radio"' in html
    assert 'No planned workout matched' in html
    assert 'Save to cardio log' in html
    assert '/garmin/import/confirm' in html
    # The inline toggle script is nonced (CSP-clean), not an onclick handler.
    assert 'csp-nonce' in html or 'nonce=' in html
    _csp_clean(html)


def test_preview_strength_auto_match(monkeypatch):
    plan_item = _FakeRow(id=7, workout_name='Lower body', sport_type='strength_training',
                         item_date='2026-06-01')
    monkeypatch.setattr(_garmin, 'find_best_match',
                        lambda db, a: {'plan_item': plan_item, 'score': 0.91,
                                       'day_offset': 0}, raising=False)
    monkeypatch.setattr(_garmin, 'candidate_plan_items',
                        lambda db, d: [], raising=False)
    client = _client(monkeypatch)
    _set_fit_import(client, {
        'log_type': 'strength',
        'data': [
            {'exercise': 'Back Squat', 'date': '2026-06-01',
             'sets': [{'reps': 5, 'weight_lbs': 225}, {'reps': 5, 'weight_lbs': 225}]},
        ],
    })
    resp = client.get('/garmin/import/preview')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # Auto-match banner + confidence chip; no disposition radios.
    assert 'Auto-matched' in html
    assert '91% match' in html
    assert 'class="disposition-radio"' not in html
    assert 'Save to training log' in html
    assert 'Back Squat' in html
    _csp_clean(html)
