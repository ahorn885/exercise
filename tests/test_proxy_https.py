"""Regression for the `http://` external-URL bug behind Vercel's TLS-terminating
edge proxy.

Vercel terminates HTTPS at the edge and forwards to the Python function over
plain HTTP, so without `ProxyFix` the WSGI `url_scheme` is 'http' and
`url_for(..., _external=True)` builds `http://` links — the password-reset /
2FA-recovery email links and OAuth `redirect_uri`s most visibly, which then
trip browser "not secure" warnings. `app.py` wraps `app.wsgi_app` in
`ProxyFix(x_proto=1, x_host=1)` so the forwarded scheme/host win.

These tests drive the REAL app through its full WSGI stack (the middleware only
runs there, not in `test_request_context`). `DATABASE_URL` is blanked so the
module-level `init_postgres()` no-ops; the probe route is auth-exempt and never
touches the DB.
"""

from __future__ import annotations

import os

os.environ.setdefault('SECRET_KEY', 'test-secret-proxyfix')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402 — env above must precede this import

from flask import jsonify, request, url_for  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

# Register a tiny scheme-echo probe on the real app so a full-stack request can
# observe the post-ProxyFix scheme + an _external URL. Idempotent across repeat
# imports; auth-exempt so the login wall doesn't redirect it (and so the gate
# short-circuits before any get_db() call).
if '_scheme_probe' not in _appmod.app.view_functions:
    @_appmod.app.route('/__scheme_probe__')
    def _scheme_probe():
        return jsonify(scheme=request.scheme,
                       external=url_for('_scheme_probe', _external=True))

    _appmod._AUTH_EXEMPT_ENDPOINTS.add('_scheme_probe')


class TestProxyFixHttps:
    def test_proxyfix_is_applied(self):
        # Structural guard: the behavioural assertions below rest on this.
        assert isinstance(_appmod.app.wsgi_app, ProxyFix)

    def test_forwarded_proto_https_yields_https_external_url(self):
        resp = _appmod.app.test_client().get(
            '/__scheme_probe__', headers={'X-Forwarded-Proto': 'https'}
        )
        data = resp.get_json()
        assert data['scheme'] == 'https'
        assert data['external'].startswith('https://'), data['external']

    def test_forwarded_host_is_honored(self):
        resp = _appmod.app.test_client().get(
            '/__scheme_probe__',
            headers={'X-Forwarded-Proto': 'https',
                     'X-Forwarded-Host': 'aidstation.example'},
        )
        assert 'https://aidstation.example/' in resp.get_json()['external']

    def test_without_forwarded_header_defaults_http(self):
        # No forwarded proto (e.g. local dev) → plain http, unchanged behaviour.
        resp = _appmod.app.test_client().get('/__scheme_probe__')
        assert resp.get_json()['scheme'] == 'http'
