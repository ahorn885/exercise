"""Whoop integration.

Phase 0: webhook stub only. Returns 200 OK for any GET/POST so the URL
checks out if Whoop probes it at form-save. Real verification (HMAC-
SHA256 over the raw body with the client secret, base64-encoded in the
`X-WHOOP-Signature` header, plus the `X-WHOOP-Signature-Timestamp`
window check) and dispatch of the event payload (`user_id`, `id`,
`type` e.g. `workout.updated`, `trace_id`) land alongside the OAuth
connect flow in the matching phase of the master plan.

The signing key is `WHOOP_CLIENT_SECRET` — same secret used for OAuth
token exchange, per Whoop's single-credential model.

Manual upload (#767 slice 4): `/whoop/import` ingests a WHOOP
`physiological_cycles.csv` (or the `.zip` export bundle) into
`provider_raw_record` (`provider='whoop'`, `data_type='daily_summary'`) so
Layer-3A `recent_wellness` reads Whoop sleep / HRV / resting-HR independent of
the (unbuilt) live OAuth/webhook path. One daily row per cycle, idempotent on
(user, provider, data_type, date) — re-dropping the same export refreshes in
place. The polished provider+format picker is slice 5; this is the minimal
working endpoint.
"""
import json

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request, url_for,
)
from werkzeug.utils import secure_filename

from database import get_db
from routes.auth import current_user_id
from whoop_csv_parser import parse_whoop_physiological_cycles

bp = Blueprint('whoop', __name__, url_prefix='/whoop')


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200


def _record_raw(db, user_id, data_type, external_id, payload):
    """Record one WHOOP daily-wellness signal into `provider_raw_record`
    (record-don't-drop, provider-tagged). Idempotent per
    (user_id, provider, data_type, external_id); `external_id` is the ISO date,
    `observed_at` mirrors it (a daily aggregate has no finer timestamp).
    Mirrors `routes.polar_ingest._record_raw` / `routes.coros_ingest._record_raw`
    so the Layer-3A reader is provider-symmetric."""
    db.execute(
        'INSERT INTO provider_raw_record '
        '(user_id, provider, data_type, external_id, observed_at, raw_payload) '
        'VALUES (?, ?, ?, ?, ?, ?::jsonb) '
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    observed_at = EXCLUDED.observed_at, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (user_id, 'whoop', data_type, external_id, external_id,
         json.dumps(payload)),
    )


def _extract_csv(raw, fname):
    """Return (csv_bytes, None) for the physiological_cycles CSV from an
    uploaded `.csv` or a `.zip` WHOOP export bundle, or (None, error)."""
    if fname.endswith('.csv'):
        return raw, None
    if fname.endswith('.zip'):
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = [
                    n for n in zf.namelist()
                    if n.lower().endswith('physiological_cycles.csv')
                ] or [
                    n for n in zf.namelist()
                    if n.lower().endswith('.csv') and 'physiological' in n.lower()
                ]
                if not names:
                    return None, 'No physiological_cycles.csv found in the zip.'
                return zf.read(names[0]), None
        except zipfile.BadZipFile:
            return None, 'That .zip could not be read.'
    return None, 'File must be a .csv (physiological_cycles.csv) or a WHOOP .zip export.'


@bp.route('/import', methods=['GET', 'POST'])
def import_wellness():
    if request.method == 'GET':
        return render_template('whoop/import.html', result=None)

    f = request.files.get('csv_file')
    if not f or not f.filename:
        flash('No file selected.', 'warning')
        return redirect(url_for('whoop.import_wellness'))

    fname = secure_filename(f.filename or '').lower()
    raw, err = _extract_csv(f.read(), fname)
    if err:
        flash(err, 'danger')
        return redirect(url_for('whoop.import_wellness'))

    try:
        records = parse_whoop_physiological_cycles(raw)
    except ValueError as exc:
        flash(f'Could not parse WHOOP CSV: {exc}', 'danger')
        return redirect(url_for('whoop.import_wellness'))

    uid = current_user_id()
    db = get_db()
    for rec in records:
        _record_raw(db, uid, 'daily_summary', rec['date'], rec)
    db.commit()
    print(  # Rule #15
        f"[whoop-import] user={uid} ingested {len(records)} day(s) "
        f"into provider_raw_record (provider=whoop, data_type=daily_summary)"
    )
    flash(f'Imported {len(records)} day(s) of WHOOP wellness.', 'success')
    return render_template('whoop/import.html', result={'days': len(records)})
