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

Manual upload (#767 slice 4 → 5): a WHOOP `physiological_cycles.csv` export is
ingested into `provider_raw_record` (`provider='whoop'`,
`data_type='daily_summary'`) so Layer-3A `recent_wellness` reads Whoop sleep /
HRV / resting-HR independent of the (unbuilt) live OAuth/webhook path. One daily
row per cycle, idempotent on (user, provider, data_type, date) — re-dropping the
same export refreshes in place. Slice 5 folded the standalone `/whoop/import`
page into the single auto-detecting uploader on the connections hub
(`routes.garmin.import_bulk`): this module now exposes the reusable writer
(`ingest_whoop_csv`) that the uploader calls when it sees a `.csv`, plus the
webhook stub.
"""
import json

from flask import Blueprint, jsonify

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


def ingest_whoop_csv(db, user_id, raw) -> int:
    """Parse a WHOOP `physiological_cycles.csv` and record each day into
    `provider_raw_record` (provider='whoop', data_type='daily_summary'). Returns
    the number of days recorded (≥1 on success). Raises `ValueError` if `raw`
    isn't a usable physiological_cycles export. Does NOT commit — the caller owns
    the transaction (the unified uploader commits per file)."""
    records = parse_whoop_physiological_cycles(raw)
    for rec in records:
        _record_raw(db, user_id, 'daily_summary', rec['date'], rec)
    return len(records)
