"""Tests for #1092 — the single-file `garmin.import_fit`/`import_confirm`
preview-and-plan-match flow accepting .tcx/.gpx, not just .fit.

Before this change the interactive single-file importer (`routes/garmin.py`
`import_fit`/`import_preview`/`import_confirm`) hard-restricted uploads to
`.fit`/`.zip`, even though the bulk drop zone (`import_bulk`) already parsed
`.tcx`/`.gpx` via `tcx_gpx_parser.py`. This covers the single-file path now
dispatching to `parse_tcx`/`parse_gpx`, auto-detecting the upload source
(`detect_source`, #1055) the same way the bulk path does, and tagging the
`provider_raw_record` corroboration row with that detected source instead of
the parser's generic 'manual' fallback.
"""

from __future__ import annotations

import io
import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-single-file-import-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402
import routes.garmin as _garmin  # noqa: E402


TCX_COROS_RUN = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
    b'<Activities><Activity Sport="Running">'
    b'<Id>2026-06-15T13:00:00Z</Id>'
    b'<Lap StartTime="2026-06-15T13:00:00Z">'
    b'<TotalTimeSeconds>600</TotalTimeSeconds>'
    b'<DistanceMeters>1609.34</DistanceMeters>'
    b'<Track><Trackpoint><Time>2026-06-15T13:00:00Z</Time>'
    b'<DistanceMeters>0</DistanceMeters></Trackpoint>'
    b'<Trackpoint><Time>2026-06-15T13:10:00Z</Time>'
    b'<DistanceMeters>1609.34</DistanceMeters></Trackpoint>'
    b'</Track></Lap></Activity></Activities>'
    b'<Author><Name>COROS App</Name></Author>'
    b'</TrainingCenterDatabase>'
)

GPX_GARMIN_RUN = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<gpx version="1.1" creator="Garmin Connect" xmlns="http://www.topografix.com/GPX/1/1">'
    b'<trk><type>running</type><trkseg>'
    b'<trkpt lat="44.9000" lon="-93.0000"><time>2026-06-15T13:00:00Z</time></trkpt>'
    b'<trkpt lat="44.9010" lon="-93.0010"><time>2026-06-15T13:10:00Z</time></trkpt>'
    b'</trkseg></trk></gpx>'
)


class _FakeRow(dict):
    pass


class _Cursor:
    lastrowid = 1

    def __init__(self, rows, calls=None, name=''):
        self._rows = rows
        self._calls = calls
        self._name = name

    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')

    def fetchall(self):
        return self._rows


class _Conn:
    """Fake DB that records every `execute` call so a test can inspect the SQL
    + bound params (e.g. the provider_raw_record insert's `provider` value)."""

    def __init__(self):
        self.calls = []

    def execute(self, sql, *a, **k):
        self.calls.append((sql, a[0] if a else k.get('params', ())))
        return _Cursor([])

    def commit(self):
        pass

    def rollback(self):
        pass


def _client(monkeypatch, conn=None):
    conn = conn or _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c, conn


# ── import_fit (upload) — extension gate + parser dispatch ─────────────────


def test_rejects_unsupported_extension(monkeypatch):
    client, _ = _client(monkeypatch)
    resp = client.post('/garmin/import',
                       data={'fit_file': (io.BytesIO(b'not an activity'), 'notes.txt')},
                       content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'File must be a .fit, .tcx, .gpx, or .zip file.' in html
    with client.session_transaction() as sess:
        assert 'fit_import' not in sess


def test_tcx_upload_dispatches_to_parse_tcx_and_detects_source(monkeypatch):
    client, _ = _client(monkeypatch)
    resp = client.post('/garmin/import',
                       data={'fit_file': (io.BytesIO(TCX_COROS_RUN), 'activity.tcx')},
                       content_type='multipart/form-data')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/garmin/import/preview')
    with client.session_transaction() as sess:
        parsed = sess['fit_import']
        assert parsed['log_type'] == 'cardio'
        assert parsed['data']['activity'] == 'Running'
        # detect_source (#1055) read the TCX <Author><Name> off the file itself.
        assert sess['fit_import_source'] == 'coros'
        # Dedup id carries the source-specific prefix, same as the bulk path.
        assert parsed['fit_dedup_id'].startswith('coros-file:')


def test_gpx_upload_defaults_to_garmin_source(monkeypatch):
    client, _ = _client(monkeypatch)
    resp = client.post('/garmin/import',
                       data={'fit_file': (io.BytesIO(GPX_GARMIN_RUN), 'activity.gpx')},
                       content_type='multipart/form-data')
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        parsed = sess['fit_import']
        assert parsed['log_type'] == 'cardio'
        assert sess['fit_import_source'] == 'garmin'
        assert parsed['fit_dedup_id'].startswith('fit:')


# ── import_confirm — provider_raw_record tagged with the detected source ───


def _set_fit_import(client, parsed, source):
    with client.session_transaction() as sess:
        sess['fit_import'] = parsed
        sess['fit_import_source'] = source
        sess['fit_name_override'] = ''
        sess['fit_notes'] = ''


def test_confirm_tags_provider_raw_record_with_detected_source(monkeypatch):
    monkeypatch.setattr(_garmin, '_record_disposition_for_import',
                        lambda *a, **k: None, raising=False)
    client, conn = _client(monkeypatch)
    parsed = {
        'log_type': 'cardio',
        'data': {
            'activity': 'Running', 'date': '2026-06-15', 'duration_min': 10,
            '_provider_raw': {'provider': 'manual', 'observed_at': '2026-06-15',
                              'bucket': 1, 'canonical_ref': 'D-002',
                              'payload': {'sport': 'running'}},
        },
        'fit_dedup_id': 'polar-file:deadbeef',
    }
    _set_fit_import(client, parsed, source='polar')
    resp = client.post('/garmin/import/confirm', data={'disposition': 'none'})
    assert resp.status_code == 302

    raw_call = next(c for c in conn.calls if 'INTO provider_raw_record' in c[0])
    params = raw_call[1]
    # (user_id, provider, data_type, external_id, ...) — provider must be the
    # detected 'polar', not the parser's generic 'manual' fallback.
    assert params[1] == 'polar'
    assert params[3] == 'polar-file:deadbeef'

    with client.session_transaction() as sess:
        assert 'fit_import' not in sess
        assert 'fit_import_source' not in sess
