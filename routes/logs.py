"""Vercel Log Drain sink + queryable read surface (issue #350).

The hard-kill backstop the #349/#352 plan-diag endpoint structurally *can't*
be. A Vercel gateway 504 / OOM kills the lambda before any Python `except`
runs, so `_advance_plan_generation` never reaches `_mark_plan_failed` and
`generation_traceback` stays NULL (the exact plan-#48 case in the issue). A
Vercel Log Drain POSTs all runtime stdout/stderr — *and* the proxy request log
carrying the 504 itself — to `/admin/logs/drain`; we persist every entry
verbatim (full line in `message`, full structured entry in `raw`, no
truncation — unlike the runtime-log MCP per CLAUDE.md Rule #14) and expose
`GET /admin/logs` for a token-authed reader to query past the app login wall.

Two distinct auth gates (mirroring the provider-webhook blueprints + the diag
endpoint):
- ingest (`POST /admin/logs/drain`): Vercel signs the raw body; we verify the
  `x-vercel-signature` HMAC-SHA1 against `LOG_DRAIN_SECRET`. No app session.
- query (`GET /admin/logs`): the same `_diag_authorized` gate as the plan-diag
  endpoint (admin session OR constant-time `DIAG_TOKEN`), so one secret unlocks
  both agent-readable diagnostic surfaces.

CSRF-exempt at the blueprint level like the provider-webhook blueprints — the
ingest POST carries a signature, not a CSRF token. Registered in `app.py`,
which also adds both endpoints to `_AUTH_EXEMPT_ENDPOINTS` (the global session
wall) so neither is shadowed by the login redirect.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, make_response, request

from database import get_db
from routes.admin import _diag_authorized

bp = Blueprint('logs', __name__, url_prefix='/admin/logs')

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 1000


def _verify_signature(raw_body: bytes, supplied_sig: str | None,
                      secret: str | None) -> bool:
    """Constant-time check of Vercel's `x-vercel-signature` (HMAC-SHA1 of the
    raw request body, keyed by the drain secret). No secret configured → no
    valid signature can exist, so reject — no open-ingest bypass, mirroring the
    diag endpoint's no-token-no-bypass stance."""
    if not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(supplied_sig or '', expected)


def _coerce_ts(entry: dict):
    """Vercel timestamps are epoch milliseconds. Prefer the proxy timestamp for
    request logs, fall back to the top-level one. Returns a tz-aware UTC
    datetime or None (the raw value is preserved in `raw` regardless)."""
    proxy = entry.get('proxy') or {}
    raw = proxy.get('timestamp')
    if raw is None:
        raw = entry.get('timestamp')
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw) / 1000.0, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _coerce_status(entry: dict):
    """The 504/OOM hard-kill surfaces as a `proxy` entry whose `statusCode` is
    the gateway result; plain function logs carry it top-level. Read proxy
    first, top-level second. Returns an int or None."""
    proxy = entry.get('proxy') or {}
    status = proxy.get('statusCode')
    if status is None:
        status = entry.get('statusCode')
    if isinstance(status, bool):  # bool is an int subclass — exclude it
        return None
    if isinstance(status, int):
        return status
    if isinstance(status, str) and status.isdigit():
        return int(status)
    return None


def _extract(entry: dict) -> dict:
    """Flatten one Vercel log entry into the indexed columns. The whole entry
    is stored verbatim in `raw`, so nothing is lost if Vercel's shape drifts —
    these columns just make the hot filters (recent / status / request) cheap.
    `log_id` falls back to a content hash when an entry lacks an `id`, so the
    `ON CONFLICT (log_id)` dedup (drains retry on non-2xx) always has a key."""
    proxy = entry.get('proxy') or {}
    log_id = entry.get('id')
    if not log_id:
        log_id = hashlib.sha1(
            json.dumps(entry, sort_keys=True, default=str).encode()
        ).hexdigest()
    return {
        'log_id': str(log_id),
        'ts': _coerce_ts(entry),
        'source': entry.get('source'),
        'log_type': entry.get('type'),
        'level': entry.get('level'),
        'deployment_id': entry.get('deploymentId'),
        'request_id': entry.get('requestId') or proxy.get('requestId'),
        'status_code': _coerce_status(entry),
        'method': proxy.get('method'),
        'path': proxy.get('path') or entry.get('path'),
        'message': entry.get('message'),
    }


def _build_logs_query(args) -> tuple[str, list]:
    """Pure builder for the `/admin/logs` read query → (sql, params). All
    filters are optional and AND-combined; results are newest-first. Factored
    out so the filter→SQL mapping is unit-testable without a live DB (mirrors
    the `_aggregate_*` helpers in routes/admin.py). `args` is any mapping with a
    `.get` (Flask's `request.args` or a plain dict)."""
    where: list[str] = []
    params: list = []

    status = args.get('status')
    if status and str(status).isdigit():
        where.append('status_code = ?')
        params.append(int(status))
    # status_min is the hard-kill hot filter: ?status_min=500 → 5xx only.
    status_min = args.get('status_min')
    if status_min and str(status_min).isdigit():
        where.append('status_code >= ?')
        params.append(int(status_min))

    for col, key in (('request_id', 'request_id'),
                     ('deployment_id', 'deployment_id'),
                     ('level', 'level'),
                     ('source', 'source')):
        val = args.get(key)
        if val:
            where.append(f'{col} = ?')
            params.append(val)

    path = args.get('path')
    if path:
        where.append('path LIKE ?')
        params.append(f'%{path}%')
    q = args.get('q')
    if q:
        where.append('message ILIKE ?')
        params.append(f'%{q}%')

    # ?minutes=N → only entries from the last N minutes. No lower bound by
    # default; the ts-DESC index + LIMIT keep an unfiltered newest-first scan
    # cheap.
    minutes = args.get('minutes')
    if minutes and str(minutes).isdigit():
        where.append("ts >= NOW() - (? || ' minutes')::interval")
        params.append(int(minutes))

    limit = _DEFAULT_LIMIT
    raw_limit = args.get('limit')
    if raw_limit and str(raw_limit).isdigit():
        limit = max(1, min(_MAX_LIMIT, int(raw_limit)))

    cols = ("log_id, ts, source, log_type, level, deployment_id, request_id, "
            "status_code, method, path, message, received_at")
    # ?full=1 also returns the verbatim structured entry (the full-fidelity
    # promise); omitted by default to keep the payload lean.
    if args.get('full'):
        cols += ", raw"
    sql = f"SELECT {cols} FROM vercel_logs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC NULLS LAST LIMIT ?"
    params.append(limit)
    return sql, params


def _with_verify(resp):
    """Echo the configured `x-vercel-verify` value as a response header. Vercel
    proves endpoint ownership when a drain is created/edited by checking we
    return this header, so attach it to every response from the ingest route."""
    verify = os.environ.get('LOG_DRAIN_VERIFY')
    if verify:
        resp.headers['x-vercel-verify'] = verify
    return resp


@bp.route('/drain', methods=['GET', 'POST'])
def drain_ingest():
    """Vercel Log Drain sink. GET is the liveness/ownership probe; POST is the
    signed log batch (a JSON array, a single object, or NDJSON)."""
    if request.method == 'GET':
        return _with_verify(make_response(jsonify(ok=True), 200))

    raw_body = request.get_data() or b''
    if not _verify_signature(raw_body,
                             request.headers.get('x-vercel-signature'),
                             os.environ.get('LOG_DRAIN_SECRET')):
        return _with_verify(make_response(jsonify(ok=False, error='signature'), 403))

    text = raw_body.decode('utf-8', 'replace')
    try:
        payload = json.loads(text) if text.strip() else []
        entries = payload if isinstance(payload, list) else [payload]
    except ValueError:
        # NDJSON delivery format: one JSON object per line.
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue

    db = get_db()
    inserted = 0
    try:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cols = _extract(entry)
            cur = db.execute(
                "INSERT INTO vercel_logs (log_id, ts, source, log_type, level, "
                "deployment_id, request_id, status_code, method, path, message, raw) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (log_id) DO NOTHING RETURNING id",
                (cols['log_id'], cols['ts'], cols['source'], cols['log_type'],
                 cols['level'], cols['deployment_id'], cols['request_id'],
                 cols['status_code'], cols['method'], cols['path'],
                 cols['message'], json.dumps(entry, default=str)),
            )
            if cur.fetchone() is not None:
                inserted += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        # Non-2xx makes Vercel retry the batch; the ON CONFLICT dedup keeps the
        # retry idempotent. Surface the cause to stdout (which the drain itself
        # then captures on the next batch).
        db.rollback()
        print(f"logs.drain_ingest: batch persist failed: {exc}")
        return _with_verify(make_response(
            jsonify(ok=False, error='persist_failed'), 500))

    return _with_verify(make_response(
        jsonify(ok=True, received=len(entries), inserted=inserted), 200))


@bp.route('', methods=['GET'])
def query_logs():
    """Token-authed read surface over the drained logs (Rule #14: readable past
    the app login so an agent debugging from outside a browser session can pull
    the real fault). Auth: admin session OR `DIAG_TOKEN` (`X-Diag-Token` header
    or `?token=`), same gate as the plan-diag endpoint."""
    if not _diag_authorized():
        abort(403)
    db = get_db()
    sql, params = _build_logs_query(request.args)
    rows = db.execute(sql, params).fetchall()
    logs = []
    for r in rows:
        entry = {
            'log_id': r['log_id'],
            'ts': str(r['ts']) if r['ts'] is not None else None,
            'source': r['source'],
            'type': r['log_type'],
            'level': r['level'],
            'deployment_id': r['deployment_id'],
            'request_id': r['request_id'],
            'status_code': r['status_code'],
            'method': r['method'],
            'path': r['path'],
            'message': r['message'],
            'received_at': str(r['received_at']) if r['received_at'] is not None else None,
        }
        if 'raw' in r:  # present only when ?full=1 added the column
            entry['raw'] = r['raw']
        logs.append(entry)
    return jsonify({'count': len(logs), 'logs': logs})
