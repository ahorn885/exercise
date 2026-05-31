"""D-77 concurrency guard + per-invocation budget tests.

Covers (a) the per-plan advance advisory lock that stops overlapping cron fires
and the progress poller from duplicate-synthesizing the same frontier week, and
(b) the per-invocation wall-clock budget that stops the Pattern-A engine starting
a block it can't finish before the function cap. Self-contained fakes — no live
Postgres, no real LLM."""
from __future__ import annotations

import time

import pytest

from routes import plan_create as pc
from layer4.generation_budget import (
    Layer4GenerationIncomplete,
    generation_deadline,
    generation_deadline_passed,
)


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


# ─── advisory-lock helper ────────────────────────────────────────────────────


def test_try_acquire_advance_lock_contract():
    class _Db:
        def __init__(self, row):
            self._row = row
            self.calls = []

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            return _Cur(self._row)

    assert pc._try_acquire_advance_lock(_Db({"locked": True}), 7) is True
    assert pc._try_acquire_advance_lock(_Db({"locked": False}), 7) is False
    # null result (the non-Postgres FakeDb default) reads as acquired (fail-open)
    assert pc._try_acquire_advance_lock(_Db(None), 7) is True

    db = _Db({"locked": True})
    pc._try_acquire_advance_lock(db, 42)
    assert db.calls[0][1] == (pc._ADVANCE_LOCK_NS, 42)
    assert "pg_try_advisory_lock" in db.calls[0][0]


def test_advance_skips_when_lock_held(monkeypatch):
    """A contended lock makes the pass no-op without running the cone."""
    monkeypatch.setattr(
        pc, "_load_plan_version",
        lambda db, uid, pvid: {
            "generation_status": "generating",
            "generation_error": None,
            "scope_start_date": None,
        },
    )

    def _must_not_run(*a, **k):
        raise AssertionError("orchestrate ran while another invocation held the lock")

    monkeypatch.setattr(pc, "orchestrate_plan_create", _must_not_run)

    class _Db:
        def execute(self, sql, params=()):
            if "pg_try_advisory_lock" in sql:
                return _Cur({"locked": False})
            return _Cur(None)

        def commit(self):
            pass

    out = pc._advance_plan_generation(_Db(), 1, 7)
    assert out["status"] == "generating"
    assert out.get("note") == "advance_in_progress_elsewhere"


def _generating_pv(*a, **k):
    return {
        "generation_status": "generating",
        "generation_error": None,
        "scope_start_date": None,
    }


def test_advance_in_progress_noop_is_logged(monkeypatch, capsys):
    """The contention no-op used to be SILENT, which is why the plan-49
    lock-starvation had to be inferred. It must now log — and still do no cone
    work (short-circuits before any synthesis)."""
    monkeypatch.setattr(pc, "_load_plan_version", _generating_pv)

    def _must_not_run(*a, **k):
        raise AssertionError("cone ran while the lock was held elsewhere")

    monkeypatch.setattr(pc, "orchestrate_plan_create", _must_not_run)

    class _Db:
        def execute(self, sql, params=()):
            return _Cur({"locked": False} if "pg_try_advisory_lock" in sql else None)

        def commit(self):
            pass

    out = pc._advance_plan_generation(_Db(), 1, 7)
    assert out == {"status": "generating", "note": "advance_in_progress_elsewhere"}
    assert "advance lock held elsewhere" in capsys.readouterr().out


def test_release_advance_lock_keyed_and_best_effort(capsys):
    """`_release_advance_lock` issues `pg_advisory_unlock` keyed to the plan,
    and a release fault is swallowed (it must never mask the pass outcome)."""
    calls = []

    class _Db:
        def execute(self, sql, params=()):
            calls.append((sql, params))
            return _Cur(None)

    pc._release_advance_lock(_Db(), 55)
    assert "pg_advisory_unlock" in calls[-1][0]
    assert calls[-1][1] == (pc._ADVANCE_LOCK_NS, 55)

    class _Boom:
        def execute(self, *a, **k):
            raise RuntimeError("connection down")

    pc._release_advance_lock(_Boom(), 1)  # must not raise
    assert "release failed" in capsys.readouterr().out


class _RecordingDb:
    """Lock acquired (True); records every SQL so a test can assert the
    advance lock is released. Tolerates any other query."""

    def __init__(self):
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        return _Cur({"locked": True} if "pg_try_advisory_lock" in sql else None)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_advance_releases_lock_on_clean_return(monkeypatch):
    """A pass that ACQUIRES the lock releases it on the way out — otherwise a
    clean return on a pooled connection leaks it and starves the plan."""
    monkeypatch.setattr(pc, "_load_plan_version", _generating_pv)
    monkeypatch.setattr(
        pc, "_advance_plan_generation_locked", lambda *a, **k: {"status": "ready"}
    )
    db = _RecordingDb()
    assert pc._advance_plan_generation(db, 1, 7) == {"status": "ready"}
    assert any("pg_advisory_unlock" in s for s in db.sql)


def test_advance_releases_lock_even_when_body_raises(monkeypatch):
    """The release is in a `finally`, so it fires even if the locked body
    raises — the lock must not survive a crashing pass on a pooled conn."""
    monkeypatch.setattr(pc, "_load_plan_version", _generating_pv)

    def _boom(*a, **k):
        raise RuntimeError("kaboom mid-cone")

    monkeypatch.setattr(pc, "_advance_plan_generation_locked", _boom)
    db = _RecordingDb()
    with pytest.raises(RuntimeError):
        pc._advance_plan_generation(db, 1, 7)
    assert any("pg_advisory_unlock" in s for s in db.sql)


# ─── per-invocation budget ───────────────────────────────────────────────────


def test_generation_deadline_passed_default_false():
    # No deadline set -> always False -> engine behavior unchanged (the property
    # that keeps every pre-existing test green).
    assert generation_deadline_passed() is False


def test_generation_deadline_expires_and_resets():
    with generation_deadline(0.02):
        assert generation_deadline_passed() is False
        time.sleep(0.05)
        assert generation_deadline_passed() is True
    # context exited -> deadline cleared
    assert generation_deadline_passed() is False


def test_generation_deadline_none_never_trips():
    with generation_deadline(None):
        time.sleep(0.01)
        assert generation_deadline_passed() is False


def test_incomplete_is_baseexception_not_swallowed_by_except_exception():
    # The whole design rests on broad `except Exception` in the synthesis path
    # NOT catching the stop signal. Lock that invariant in.
    assert issubclass(Layer4GenerationIncomplete, BaseException)
    assert not issubclass(Layer4GenerationIncomplete, Exception)
    caught = False
    try:
        try:
            raise Layer4GenerationIncomplete(blocks_cached=3)
        except Exception:  # noqa: BLE001 - intentionally testing it does NOT catch
            caught = True
    except Layer4GenerationIncomplete as exc:
        assert exc.blocks_cached == 3
    assert caught is False


def test_advance_budget_incomplete_keeps_generating(monkeypatch):
    """When the engine raises Layer4GenerationIncomplete mid-pass, the route keeps
    the row 'generating' (not failed) so the next pass resumes from the cache."""
    monkeypatch.setattr(
        pc, "_load_plan_version",
        lambda db, uid, pvid: {
            "generation_status": "generating",
            "generation_error": None,
            "scope_start_date": None,
        },
    )
    monkeypatch.setattr(pc, "_count_cached_blocks", lambda *a, **k: 2)
    monkeypatch.setattr(pc, "_generation_stalled", lambda *a, **k: False)
    monkeypatch.setattr(pc, "_build_layer4_cache", lambda: "CACHE")

    def _raise_incomplete(*a, **k):
        raise Layer4GenerationIncomplete(blocks_cached=2)

    monkeypatch.setattr(pc, "orchestrate_plan_create", _raise_incomplete)

    class _Db:
        def execute(self, sql, params=()):
            if "pg_try_advisory_lock" in sql:
                return _Cur({"locked": True})
            return _Cur(None)

        def commit(self):
            pass

    out = pc._advance_plan_generation(_Db(), 1, 7)
    assert out["status"] == "generating"
    assert out.get("note") == "budget_partial_progress"
