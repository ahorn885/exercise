"""Route-level regression for the global login wall (`_require_login` in
`app.py`) vs. the token-readable plan-gen diag endpoint.

Background — the shadowing bug this guards against:
    `routes/admin.py:plan_diag` (`GET /admin/plan/<id>/diag`) is *designed* to
    be readable WITHOUT the app login: an operator/agent debugging from outside
    a browser session authenticates with the `DIAG_TOKEN` secret (header
    `X-Diag-Token` or `?token=`), verified INSIDE the route by
    `_diag_authorized()`. But the app-wide `@app.before_request` `_require_login`
    gate runs *before* any route, and it redirects every non-exempt endpoint to
    the sign-in page. `admin.plan_diag` was missing from `_AUTH_EXEMPT_ENDPOINTS`,
    so the global wall shadowed the in-route token check — the endpoint was only
    ever reachable by a logged-in admin, defeating its whole purpose. The #349
    coverage was a pure helper unit test (`TestDiagTokenOk`) plus a manual §5.0
    smoke that was never actually run against the wired app, so the integration
    gap slipped to production.

These tests exercise the REAL `app` test client (gate + blueprint wired
together), which is the only place the bug is observable. The module-level
`init_postgres()` in `app.py` is neutralized by pointing `DATABASE_URL` at a
fast-failing value so the import doesn't block on the (egress-blocked) Neon
host — the assertions below all resolve on paths that short-circuit before any
`get_db()` call (the gate redirect, or the route's `abort(403)`).
"""

from __future__ import annotations

import os

# Must be set BEFORE importing `app` — they are read at module-import time.
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-auth-gate-tests')
# Force a fast-failing DB URL so app.py's module-level init_postgres() raises
# immediately (it's caught + skipped) instead of hanging on a real-but-
# unreachable Postgres host. No test here touches the DB.
os.environ['DATABASE_URL'] = ''
# Deterministic token so the "wrong token" path is unambiguous.
_DIAG_TOKEN = 'auth-gate-test-diag-token'
os.environ['DIAG_TOKEN'] = _DIAG_TOKEN

import app as _appmod  # noqa: E402 — env above must precede this import


class TestDiagEndpointBypassesLoginWall:
    """`/admin/plan/<id>/diag` must NOT be shadowed by the global login wall;
    its token auth runs in-route, like the cron/webhook endpoints."""

    URL = '/admin/plan/999999/diag'

    def _client(self):
        return _appmod.app.test_client()

    def test_listed_in_auth_exempt_endpoints(self):
        # Structural guard: the exemption is what lets the in-route token check
        # ever run. If this regresses, the behavioral assertions below do too.
        assert 'admin.plan_diag' in _appmod._AUTH_EXEMPT_ENDPOINTS

    def test_wrong_token_reaches_route_and_403s_not_redirect(self):
        # THE regression: pre-fix this was a 302 -> /auth/login (gate shadowed
        # the route). Post-fix the route is reached and its _diag_authorized()
        # denies with a 403 — no login redirect.
        resp = self._client().get(self.URL + '?token=wrong')
        assert resp.status_code == 403
        assert resp.headers.get('Location') is None

    def test_no_token_403s_not_redirect(self):
        resp = self._client().get(self.URL)
        assert resp.status_code == 403
        assert resp.headers.get('Location') is None


class TestInspectStaysBehindLoginWall:
    """The HTML inspect page is admin-only (no token surface), so it must stay
    behind the global wall — the exemption is scoped to the JSON diag endpoint
    alone, not all of `/admin/plan/<id>/*`."""

    def test_inspect_unauthed_redirects_to_login(self):
        resp = _appmod.app.test_client().get('/admin/plan/999999/inspect')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers.get('Location', '')
