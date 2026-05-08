import os
import sqlite3

from flask import g, current_app

DATABASE_URL = os.environ.get('DATABASE_URL')


def _is_postgres():
    return bool(DATABASE_URL)


def _on_vercel() -> bool:
    """True when running inside a Vercel serverless function.

    Vercel sets VERCEL=1; AWS_LAMBDA_FUNCTION_NAME is the underlying Lambda
    signal. Either is sufficient to mean: the package directory is read-only
    and only /tmp is writable.
    """
    return bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))


def sqlite_path() -> str:
    """Single source of truth for the SQLite file location.

    On Vercel the package dir is read-only, so writes have to go to /tmp
    (ephemeral, but it's all we have until DATABASE_URL points at Neon).
    Locally we keep the historical instance/ path.
    """
    if _on_vercel():
        return '/tmp/training.db'
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'training.db')


class _PgRow(dict):
    """Dict that also supports integer indexing, matching sqlite3.Row behaviour."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _CompatCursor:
    """Wraps a psycopg2 RealDictCursor to match sqlite3's interface."""
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


class _PgConn:
    """Thin wrapper around a psycopg2 connection that accepts ? placeholders."""
    def __init__(self, conn):
        import psycopg2.extras
        self._conn = conn
        self._extras = psycopg2.extras

    def execute(self, sql, params=()):
        sql = sql.replace('?', '%s')
        cur = self._conn.cursor(cursor_factory=self._extras.RealDictCursor)
        cur.execute(sql, params)
        return _CompatCursor(cur)

    def executemany(self, sql, param_list):
        sql = sql.replace('?', '%s')
        cur = self._conn.cursor()
        cur.executemany(sql, param_list)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db():
    if 'db' not in g:
        if _is_postgres():
            import psycopg2
            raw = psycopg2.connect(DATABASE_URL)
            g.db = _PgConn(raw)
        else:
            raw = sqlite3.connect(current_app.config['DATABASE'])
            raw.row_factory = sqlite3.Row
            raw.execute('PRAGMA foreign_keys = ON')
            g.db = raw
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
