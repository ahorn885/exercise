import os

from flask import g

DATABASE_URL = os.environ.get('DATABASE_URL')

# libpq TCP keepalives. A Layer 4 block synthesis runs for minutes with no DB
# traffic while the Anthropic call is in flight, so the request's connection
# sits idle long enough for Neon's proxy to drop the SSL connection; the next
# statement (the per-block cache `put`) then raises
# `OperationalError: SSL connection has been closed unexpectedly`. Keepalives
# keep the idle connection alive; the reconnect-retry in `_PgConn` heals any
# drop that still slips through. (Defense-in-depth — D-77 plan-gen.)
_KEEPALIVE_ARGS = dict(
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5,
)


def _connect():
    """Open a raw psycopg2 connection with keepalives. Single place so the
    initial connect and the reconnect-on-drop path use identical settings."""
    import psycopg2
    return psycopg2.connect(DATABASE_URL, **_KEEPALIVE_ARGS)


class _PgRow(dict):
    """Dict that also supports integer indexing, matching sqlite3.Row behaviour."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _CompatCursor:
    """Wraps a psycopg2 RealDictCursor to match sqlite3.Row's interface so
    callers can use `row['col']` and `row[0]` interchangeably."""
    def __init__(self, cursor):
        self._c = cursor

    def fetchone(self):
        row = self._c.fetchone()
        return _PgRow(row) if row else None

    def fetchall(self):
        return [_PgRow(row) for row in self._c.fetchall()]

    @property
    def lastrowid(self):
        row = self._c.fetchone()
        return list(row.values())[0] if row else None

    @property
    def rowcount(self):
        """Rows affected by the last statement, off the wrapped psycopg2
        cursor. UPDATE/DELETE callers branch on it (provider_identity
        link/unlink, provider_auth.disconnect, account_merge); without it they
        raise AttributeError on `cur.rowcount`. RETURNING-based callers use
        fetchone()/lastrowid instead (see routes/garmin.py)."""
        return self._c.rowcount


class _PgConn:
    """Thin wrapper around a psycopg2 connection that accepts ? placeholders
    so callers can keep the historical SQLite-flavoured placeholder syntax.

    Survives Neon dropping an idle connection mid-request (see `_KEEPALIVE_ARGS`):
    a statement that fails because the connection is gone reopens a fresh
    connection and retries once. The dropped statement never reached the server,
    so the retry is safe; the app's writes are idempotent regardless (the cache
    `put` is an ON CONFLICT upsert; the plan_versions status flips are
    by-id UPDATEs)."""
    def __init__(self, conn):
        import psycopg2
        import psycopg2.extras
        self._conn = conn
        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras

    def _connection_dropped(self, exc) -> bool:
        # OperationalError ("SSL connection has been closed unexpectedly",
        # "server closed the connection unexpectedly") and InterfaceError
        # ("connection already closed") are the lost-connection signals. A
        # genuinely-bad statement re-raises on the single retry below.
        return isinstance(
            exc, (self._psycopg2.OperationalError, self._psycopg2.InterfaceError)
        )

    def _reopen(self):
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = _connect()

    def execute(self, sql, params=()):
        sql = sql.replace('?', '%s')
        try:
            cur = self._conn.cursor(cursor_factory=self._extras.RealDictCursor)
            cur.execute(sql, params)
        except Exception as exc:
            if not self._connection_dropped(exc):
                raise
            self._reopen()
            cur = self._conn.cursor(cursor_factory=self._extras.RealDictCursor)
            cur.execute(sql, params)
        return _CompatCursor(cur)

    def executemany(self, sql, param_list):
        sql = sql.replace('?', '%s')
        try:
            cur = self._conn.cursor()
            cur.executemany(sql, param_list)
        except Exception as exc:
            if not self._connection_dropped(exc):
                raise
            self._reopen()
            cur = self._conn.cursor()
            cur.executemany(sql, param_list)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception as exc:
            # A rollback on a dropped connection raised
            # `InterfaceError: connection already closed`, which escaped the
            # route's failure handler (`_mark_plan_failed` rolls back first) and
            # turned a recoverable fault into a 500 with the plan_versions row
            # stuck 'generating'. There's nothing to roll back on a dead
            # connection — reopen a clean one so the caller's next statement
            # (the failure UPDATE) runs instead of re-raising.
            if not self._connection_dropped(exc):
                raise
            self._reopen()

    def close(self):
        self._conn.close()


def get_db():
    if 'db' not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                'DATABASE_URL environment variable is required. Set it to '
                'your Neon (or other PostgreSQL) connection string before '
                'starting the app.'
            )
        g.db = _PgConn(_connect())
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
