"""Regression tests for `database._PgConn`'s reconnect-on-drop behaviour.

Context (D-77 plan-gen): a Layer 4 block synthesis runs for minutes with no DB
traffic while the Anthropic call is in flight, so the request's Postgres
connection sits idle long enough for Neon's proxy to drop the SSL link. The
next statement — the per-block cache `put` — then raised
`OperationalError: SSL connection has been closed unexpectedly`, the accepted
block was never cached, and `_mark_plan_failed`'s `db.rollback()` on the dead
connection raised `InterfaceError: connection already closed`, escaping as a
500 with the plan_versions row stuck 'generating'. These tests pin the fix:
`execute`/`executemany` reopen + retry once on a dropped connection, and
`rollback` reopens instead of re-raising.
"""
import psycopg2
import pytest

import database


class _FakeCursor:
    def __init__(self, execute_error=None):
        self._execute_error = execute_error
        self.executed = []

    def execute(self, sql, params=None):
        if self._execute_error is not None:
            raise self._execute_error
        self.executed.append((sql, params))

    def executemany(self, sql, param_list):
        if self._execute_error is not None:
            raise self._execute_error
        self.executed.append((sql, list(param_list)))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConn:
    """Minimal stand-in for a psycopg2 connection.

    `cursor_error` is raised by the cursor's execute (simulating a dead
    connection surfacing on the statement); `rollback_error` is raised by
    rollback (simulating a dead connection surfacing on rollback).
    """
    def __init__(self, *, cursor_error=None, rollback_error=None):
        self._cursor_error = cursor_error
        self._rollback_error = rollback_error
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self, cursor_factory=None):
        return _FakeCursor(execute_error=self._cursor_error)

    def commit(self):
        self.committed = True

    def rollback(self):
        if self._rollback_error is not None:
            raise self._rollback_error
        self.rolled_back = True

    def close(self):
        self.closed = True


def _patch_reconnect(monkeypatch, fresh_conn):
    """Make `database._connect` hand back `fresh_conn` on the next reopen."""
    calls = {"n": 0}

    def fake_connect():
        calls["n"] += 1
        return fresh_conn

    monkeypatch.setattr(database, "_connect", fake_connect)
    return calls


def test_execute_reconnects_and_retries_on_dropped_connection(monkeypatch):
    dropped = _FakeConn(
        cursor_error=psycopg2.OperationalError(
            "SSL connection has been closed unexpectedly"
        )
    )
    fresh = _FakeConn()
    calls = _patch_reconnect(monkeypatch, fresh)

    conn = database._PgConn(dropped)
    result = conn.execute("INSERT INTO layer4_cache VALUES (?)", ("x",))

    assert calls["n"] == 1, "should have reopened exactly once"
    assert dropped.closed, "stale connection should be closed on reopen"
    assert conn._conn is fresh, "should swap to the fresh connection"
    # The retried statement landed on the fresh connection; commit follows it.
    conn.commit()
    assert fresh.committed
    assert result is not None


def test_execute_does_not_retry_on_non_connection_error(monkeypatch):
    # A genuine bad statement (not a dropped connection) must surface, not retry.
    bad = _FakeConn(cursor_error=psycopg2.ProgrammingError("syntax error"))
    calls = _patch_reconnect(monkeypatch, _FakeConn())

    conn = database._PgConn(bad)
    with pytest.raises(psycopg2.ProgrammingError):
        conn.execute("SELCT 1")
    assert calls["n"] == 0, "must not reconnect on a non-connection error"


def test_rollback_reopens_on_dropped_connection(monkeypatch):
    dead = _FakeConn(
        rollback_error=psycopg2.InterfaceError("connection already closed")
    )
    fresh = _FakeConn()
    calls = _patch_reconnect(monkeypatch, fresh)

    conn = database._PgConn(dead)
    # Must not raise — this is the path _mark_plan_failed relies on.
    conn.rollback()

    assert calls["n"] == 1
    assert conn._conn is fresh
    # And the subsequent failure UPDATE + commit run on the live connection.
    conn.execute("UPDATE plan_versions SET generation_status = 'failed'")
    conn.commit()
    assert fresh.committed


def test_rollback_propagates_non_connection_error(monkeypatch):
    other = _FakeConn(rollback_error=psycopg2.ProgrammingError("boom"))
    calls = _patch_reconnect(monkeypatch, _FakeConn())

    conn = database._PgConn(other)
    with pytest.raises(psycopg2.ProgrammingError):
        conn.rollback()
    assert calls["n"] == 0


def test_executemany_reconnects_and_retries(monkeypatch):
    dropped = _FakeConn(
        cursor_error=psycopg2.OperationalError("server closed the connection")
    )
    fresh = _FakeConn()
    calls = _patch_reconnect(monkeypatch, fresh)

    conn = database._PgConn(dropped)
    conn.executemany("INSERT INTO t VALUES (?)", [("a",), ("b",)])

    assert calls["n"] == 1
    assert conn._conn is fresh
