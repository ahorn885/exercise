"""Tests for `evidence_repo` — the #826 science-provenance data-access layer.

Uses a minimal `_FakeConn` (records `execute` calls + serves queued rows in
FIFO order) in the style of `tests/test_plan_nutrition_repo.py` and
`tests/test_routes_admin.py`. No live DB — the contracts under test are the SQL
shape and the link-vs-flag branching, not the engine.
"""

from __future__ import annotations

import pytest

import evidence_repo as er


# ─── fakes ───────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None, rowcount=None):
        self._row = row
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchone(self):
        return _FakeRow(self._row) if self._row is not None else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self._responses: list[tuple] = []
        self.commits = 0

    def queue(self, row=None, rows=None, rowcount=None):
        self._responses.append((row, rows, rowcount))
        return self

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self._responses:
            row, rows, rowcount = self._responses.pop(0)
            return _FakeCursor(row=row, rows=rows, rowcount=rowcount)
        return _FakeCursor()

    def commit(self):
        self.commits += 1


def _sql(call) -> str:
    return " ".join(call[0].split())


# ─── reads ───────────────────────────────────────────────────────────────────


def test_resolve_slugs_to_ids_only_keeps_hits():
    """A slug present + active resolves; one absent (None row) is dropped —
    the constrained-citation rule."""
    db = _FakeConn()
    db.queue(row={"id": 7})   # 'polarized-intensity' hits
    db.queue(row=None)        # 'made-up' misses
    out = er.resolve_slugs_to_ids(db, ["polarized-intensity", "made-up"])
    assert out == {"polarized-intensity": 7}
    # Each lookup constrains to active sources.
    assert "status = 'active'" in _sql(db.calls[0])


def test_list_baseline_source_ids():
    db = _FakeConn()
    db.queue(rows=[{"id": 1}, {"id": 2}, {"id": 3}])
    assert er.list_baseline_source_ids(db) == [1, 2, 3]
    assert "is_baseline = TRUE" in _sql(db.calls[0])
    assert "status = 'active'" in _sql(db.calls[0])


def test_load_plan_evidence_joins_and_orders():
    db = _FakeConn()
    db.queue(rows=[
        {"id": 1, "slug": "a", "kind": "study", "title": "T", "summary": None,
         "citation": None, "url": None, "status": "active", "is_baseline": True},
    ])
    out = er.load_plan_evidence(db, 99)
    assert out[0]["slug"] == "a"
    sql = _sql(db.calls[0])
    assert "JOIN evidence_sources" in sql
    assert "pve.plan_version_id = ?" in sql
    assert db.calls[0][1] == (99,)


# ─── link writes ─────────────────────────────────────────────────────────────


def test_link_plan_evidence_idempotent_insert():
    db = _FakeConn()
    db.queue(rowcount=1)
    db.queue(rowcount=0)  # conflict — already linked
    written = er.link_plan_evidence(db, 99, [1, 2])
    assert written == 1
    assert "ON CONFLICT (plan_version_id, evidence_source_id) DO NOTHING" in _sql(db.calls[0])
    assert db.calls[0][1] == (99, 1)
    assert db.calls[1][1] == (99, 2)


def test_attach_baseline_plan_evidence_links_baseline_set():
    db = _FakeConn()
    db.queue(rows=[{"id": 5}, {"id": 6}])  # baseline ids
    db.queue(rowcount=1)                   # link 5
    db.queue(rowcount=1)                   # link 6
    n = er.attach_baseline_plan_evidence(db, 42)
    assert n == 2
    # one SELECT for baselines + two link INSERTs.
    assert len(db.calls) == 3
    assert db.calls[1][1] == (42, 5)
    assert db.calls[2][1] == (42, 6)


def test_attach_baseline_no_sources_is_noop():
    db = _FakeConn()
    db.queue(rows=[])  # no baseline sources seeded
    assert er.attach_baseline_plan_evidence(db, 42) == 0
    assert len(db.calls) == 1  # only the SELECT, no inserts


# ─── cited path: link vs flag ────────────────────────────────────────────────


def test_record_citations_links_hits_and_flags_misses():
    db = _FakeConn()
    # resolve_slugs_to_ids: two lookups
    db.queue(row={"id": 11})  # 'tapering-peak' hits
    db.queue(row=None)        # 'heat-accl' misses
    # record_curation_flag for the miss: SELECT existing (none) then INSERT
    db.queue(row=None)        # no existing open flag
    db.queue()               # INSERT flag
    # link_plan_evidence for the hit
    db.queue(rowcount=1)

    out = er.record_plan_evidence_citations(
        db, 99, "layer3b",
        [
            {"slug": "tapering-peak", "context_text": "taper shape"},
            {"slug": "heat-accl", "context_text": "heat plan"},
        ],
    )
    assert out == {"linked": 1, "flagged": 1}
    # A flag INSERT happened with the missing token + layer.
    flag_inserts = [c for c in db.calls if "INSERT INTO evidence_curation_flags" in c[0]]
    assert flag_inserts
    assert "heat-accl" in flag_inserts[0][1]
    assert "layer3b" in flag_inserts[0][1]


def test_record_curation_flag_increments_existing():
    db = _FakeConn()
    db.queue(row={"id": 3})  # existing open flag found
    er.record_curation_flag(
        db, plan_version_id=1, raised_by_layer="layer2",
        context_text="ctx", cited_token="tok",
    )
    sqls = [_sql(c) for c in db.calls]
    assert any("occurrences = occurrences + 1" in s for s in sqls)
    assert not any("INSERT INTO evidence_curation_flags" in s for s in sqls)


def test_record_curation_flag_inserts_when_absent():
    db = _FakeConn()
    db.queue(row=None)  # no existing flag
    db.queue()          # INSERT
    er.record_curation_flag(
        db, plan_version_id=None, raised_by_layer=None,
        context_text="ctx", cited_token=None,
    )
    assert any("INSERT INTO evidence_curation_flags" in c[0] for c in db.calls)


# ─── curation-flag admin writes ──────────────────────────────────────────────


def test_resolve_and_dismiss_curation_flag_sql():
    db = _FakeConn()
    er.resolve_curation_flag(db, 5, 9)
    assert "status = 'resolved'" in _sql(db.calls[0])
    assert db.calls[0][1] == (9, 5)

    db2 = _FakeConn()
    er.dismiss_curation_flag(db2, 7)
    assert "status = 'dismissed'" in _sql(db2.calls[0])
    assert db2.calls[0][1] == (7,)


def test_count_open_curation_flags():
    db = _FakeConn()
    db.queue(row={"n": 4})
    assert er.count_open_curation_flags(db) == 4


# ─── source authoring ────────────────────────────────────────────────────────


def test_create_evidence_source_returns_id():
    db = _FakeConn()
    db.queue(row={"id": 21})
    sid = er.create_evidence_source(
        db, slug="heat-acclimation", kind="study", title="Heat acclimation",
    )
    assert sid == 21
    assert "INSERT INTO evidence_sources" in db.calls[0][0]


def test_create_evidence_source_rejects_bad_kind():
    db = _FakeConn()
    with pytest.raises(ValueError):
        er.create_evidence_source(
            db, slug="x", kind="blog_post", title="nope",
        )
    assert db.calls == []  # validation precedes any DB work
