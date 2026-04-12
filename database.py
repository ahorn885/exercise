import os
import sqlite3

from flask import g, current_app

DATABASE_URL = os.environ.get('DATABASE_URL')


def _is_postgres():
    return bool(DATABASE_URL)


class _CompatCursor:
    """Wraps a psycopg2 RealDictCursor to match sqlite3's interface."""
    def __init__(self, cursor):
        self._c = cursor

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()

    @property
    def lastrowid(self):
        return self._c.fetchone()[0] if self._c.description else None


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
