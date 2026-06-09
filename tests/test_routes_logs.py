"""Tests for the Vercel Log Drain sink + reader (issue #350, routes/logs.py).

Coverage (pure helpers — route smoke is deferred to manual §5.0 per the
`tests/test_routes_admin.py` precedent for token-gated/webhook routes):
- `_verify_signature` — HMAC-SHA1 constant-time gate; no-secret denies.
- `_coerce_ts` — epoch-ms → tz-aware UTC, proxy-first, None-tolerant.
- `_coerce_status` — proxy-first status, bool/garbage rejected.
- `_extract` — entry → indexed columns; id fallback to content hash.
- `_build_logs_query` — filter→SQL mapping, newest-first, limit clamp.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from flask import Flask, make_response

from routes.logs import (
    _DRAIN_PATH,
    _build_logs_query,
    _coerce_status,
    _coerce_ts,
    _extract,
    _is_drain_self_log,
    _verify_signature,
    _with_verify,
)


# ─── _is_drain_self_log (feedback-loop guard) ────────────────────────────────


class TestIsDrainSelfLog:
    """The drain's own delivery POSTs emit a proxy request log that the next
    batch would re-ingest forever — `_is_drain_self_log` flags those so ingest
    drops them."""

    def test_drain_path_is_self_log(self):
        assert _is_drain_self_log(_DRAIN_PATH) is True
        assert _is_drain_self_log('/admin/logs/drain') is True

    def test_other_paths_kept(self):
        assert _is_drain_self_log('/plans/v2/48/generate') is False
        assert _is_drain_self_log('/admin/logs') is False  # the reader, not a loop
        assert _is_drain_self_log(None) is False  # stdout lines carry no path


# ─── _with_verify (Vercel ownership handshake) ───────────────────────────────


class TestWithVerify:
    """`_with_verify(resp)` attaches the `x-vercel-verify` ownership header.
    Echoes the incoming request header first (so drain verification passes with
    no pre-shared token / redeploy), env var second."""

    def test_echoes_incoming_request_header(self):
        app = Flask(__name__)
        with app.test_request_context(headers={'x-vercel-verify': 'incoming-tok'}):
            resp = _with_verify(make_response('', 200))
            assert resp.headers.get('x-vercel-verify') == 'incoming-tok'

    def test_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv('LOG_DRAIN_VERIFY', 'env-tok')
        app = Flask(__name__)
        with app.test_request_context():  # no incoming header
            resp = _with_verify(make_response('', 200))
            assert resp.headers.get('x-vercel-verify') == 'env-tok'

    def test_incoming_header_wins_over_env(self, monkeypatch):
        monkeypatch.setenv('LOG_DRAIN_VERIFY', 'env-tok')
        app = Flask(__name__)
        with app.test_request_context(headers={'x-vercel-verify': 'incoming-tok'}):
            resp = _with_verify(make_response('', 200))
            assert resp.headers.get('x-vercel-verify') == 'incoming-tok'

    def test_no_token_no_header(self, monkeypatch):
        monkeypatch.delenv('LOG_DRAIN_VERIFY', raising=False)
        app = Flask(__name__)
        with app.test_request_context():
            resp = _with_verify(make_response('', 200))
            assert 'x-vercel-verify' not in resp.headers


# ─── _verify_signature ───────────────────────────────────────────────────────


class TestVerifySignature:
    _BODY = b'[{"id":"a","message":"hi"}]'

    def _sig(self, secret: str) -> str:
        return hmac.new(secret.encode(), self._BODY, hashlib.sha1).hexdigest()

    def test_no_secret_denies_even_with_signature(self):
        # Mirrors the diag endpoint: no secret configured → no valid signature
        # exists, so the ingest endpoint is not an open sink.
        assert _verify_signature(self._BODY, self._sig('s'), None) is False
        assert _verify_signature(self._BODY, self._sig('s'), '') is False

    def test_missing_or_wrong_signature_denied(self):
        assert _verify_signature(self._BODY, None, 'secret') is False
        assert _verify_signature(self._BODY, '', 'secret') is False
        assert _verify_signature(self._BODY, 'deadbeef', 'secret') is False

    def test_matching_signature_authorizes(self):
        assert _verify_signature(self._BODY, self._sig('secret'), 'secret') is True

    def test_body_tamper_invalidates(self):
        sig = self._sig('secret')
        assert _verify_signature(self._BODY + b' ', sig, 'secret') is False


# ─── _coerce_ts ──────────────────────────────────────────────────────────────


class TestCoerceTs:
    def test_top_level_epoch_ms(self):
        # 2026-05-31T15:50:42Z → 1748706642000 ms.
        ms = 1748706642000
        out = _coerce_ts({'timestamp': ms})
        assert out == datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        assert out.tzinfo is timezone.utc

    def test_proxy_timestamp_preferred(self):
        out = _coerce_ts({'timestamp': 1000, 'proxy': {'timestamp': 2000}})
        assert out == datetime.fromtimestamp(2.0, tz=timezone.utc)

    def test_missing_returns_none(self):
        assert _coerce_ts({}) is None

    def test_garbage_returns_none(self):
        assert _coerce_ts({'timestamp': 'not-a-number'}) is None


# ─── _coerce_status ──────────────────────────────────────────────────────────


class TestCoerceStatus:
    def test_proxy_status_preferred(self):
        # The plan-#48 hard-kill shape: a proxy entry carrying the gateway 504.
        assert _coerce_status({'proxy': {'statusCode': 504}}) == 504

    def test_top_level_fallback(self):
        assert _coerce_status({'statusCode': 200}) == 200

    def test_string_digits_coerced(self):
        assert _coerce_status({'statusCode': '500'}) == 500

    def test_bool_rejected(self):
        # bool is an int subclass — must not slip through as 0/1.
        assert _coerce_status({'statusCode': True}) is None

    def test_missing_or_garbage_none(self):
        assert _coerce_status({}) is None
        assert _coerce_status({'statusCode': 'x'}) is None


# ─── _extract ────────────────────────────────────────────────────────────────


class TestExtract:
    def test_proxy_request_log(self):
        entry = {
            'id': 'log-1',
            'timestamp': 1748706642000,
            'source': 'lambda',
            'type': 'stdout',
            'level': 'error',
            'deploymentId': 'dpl_x',
            'requestId': 'req_1',
            'message': 'POST /plans/v2/48/generate',
            'proxy': {'method': 'POST', 'path': '/plans/v2/48/generate',
                      'statusCode': 504},
        }
        out = _extract(entry)
        assert out['log_id'] == 'log-1'
        assert out['status_code'] == 504
        assert out['method'] == 'POST'
        assert out['path'] == '/plans/v2/48/generate'
        assert out['request_id'] == 'req_1'
        assert out['source'] == 'lambda'
        assert out['log_type'] == 'stdout'
        assert out['deployment_id'] == 'dpl_x'
        assert out['ts'] == datetime.fromtimestamp(1748706642.0, tz=timezone.utc)

    def test_missing_id_falls_back_to_content_hash(self):
        entry = {'message': 'no id here', 'timestamp': 1000}
        out = _extract(entry)
        expected = hashlib.sha1(
            __import__('json').dumps(entry, sort_keys=True, default=str).encode()
        ).hexdigest()
        assert out['log_id'] == expected

    def test_request_id_falls_back_to_proxy(self):
        out = _extract({'proxy': {'requestId': 'rp'}})
        assert out['request_id'] == 'rp'

    def test_sparse_entry_all_optional_none(self):
        out = _extract({'id': 'x', 'raw': 'ignored'})
        assert out['log_id'] == 'x'
        for k in ('ts', 'source', 'log_type', 'level', 'deployment_id',
                  'request_id', 'status_code', 'method', 'path', 'message'):
            assert out[k] is None


# ─── _build_logs_query ───────────────────────────────────────────────────────


class TestBuildLogsQuery:
    def test_no_filters_newest_first_default_limit(self):
        sql, params = _build_logs_query({})
        assert 'FROM vercel_logs' in sql
        assert 'WHERE' not in sql
        assert 'ORDER BY ts DESC NULLS LAST' in sql
        assert sql.strip().endswith('LIMIT ?')
        assert params == [100]
        assert ', raw' not in sql  # raw withheld unless ?full

    def test_status_min_hard_kill_filter(self):
        sql, params = _build_logs_query({'status_min': '500'})
        assert 'status_code >= ?' in sql
        assert params == [500, 100]

    def test_exact_status(self):
        sql, params = _build_logs_query({'status': '504'})
        assert 'status_code = ?' in sql
        assert params == [504, 100]

    def test_request_and_text_filters_combined(self):
        sql, params = _build_logs_query({'request_id': 'req_1', 'q': 'Traceback'})
        assert 'request_id = ?' in sql
        assert 'message ILIKE ?' in sql
        assert params == ['req_1', '%Traceback%', 100]

    def test_path_like_and_minutes_window(self):
        sql, params = _build_logs_query({'path': '/plans', 'minutes': '30'})
        assert 'path LIKE ?' in sql
        assert "ts >= NOW() - (? || ' minutes')::interval" in sql
        assert params == ['%/plans%', 30, 100]

    def test_limit_clamped_to_max(self):
        _, params = _build_logs_query({'limit': '99999'})
        assert params == [1000]

    def test_limit_floor_one(self):
        _, params = _build_logs_query({'limit': '0'})
        assert params == [1]

    def test_non_numeric_limit_ignored(self):
        _, params = _build_logs_query({'limit': 'abc'})
        assert params == [100]

    def test_full_adds_raw_column(self):
        sql, params = _build_logs_query({'full': '1'})
        assert ', raw' in sql
        assert params == [100]

    def test_level_and_source_filters(self):
        sql, params = _build_logs_query({'level': 'error', 'source': 'lambda'})
        assert 'level = ?' in sql
        assert 'source = ?' in sql
        assert params == ['error', 'lambda', 100]
