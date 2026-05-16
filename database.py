import os

from flask import g

DATABASE_URL = os.environ.get('DATABASE_URL')


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


class _PgConn:
    """Thin wrapper around a psycopg2 connection that accepts ? placeholders
    so callers can keep the historical SQLite-flavoured placeholder syntax."""
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
        if not DATABASE_URL:
            raise RuntimeError(
                'DATABASE_URL environment variable is required. Set it to '
                'your Neon (or other PostgreSQL) connection string before '
                'starting the app.'
            )
        import psycopg2
        raw = psycopg2.connect(DATABASE_URL)
        g.db = _PgConn(raw)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
