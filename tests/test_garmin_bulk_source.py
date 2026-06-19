"""Tests for manual-upload source generalization (#767 slice 1).

The bulk FIT drop zone now ingests activities exported from non-Garmin services.
A `source` form field selects which provider-id column the per-file content-hash
lands in, and a source-specific dedup prefix namespaces those hashes so they
never collide across providers. Garmin stays the default.

Covers:
  - `_SOURCE_MAP` / `_source_column` / `_source_prefix` — the source allowlist.
  - `_fit_dedup_id` — parameterized prefix (default 'fit:').
  - `_bulk_insert_cardio` — writes `gid` to the source's column + tags the
    corroboration `provider_raw_record` row with the source.
  - `_bulk_insert_strength` — writes to the source's column (cardio's twin).
  - `_already_imported` — dedups against the source's column; Strava skips the
    strength table (no strava column there; Strava exports no strength FITs).
"""

import json

import pytest

import routes.garmin as g
from routes.garmin import (
    _SOURCE_MAP,
    _already_imported,
    _bulk_insert_cardio,
    _bulk_insert_strength,
    _fit_dedup_id,
    _source_column,
    _source_prefix,
)


class _FakeCursor:
    lastrowid = 1

    def fetchone(self):
        return None


class _FakeConn:
    """Records SQL; fetchone returns whatever `rows` queue yields (default None)."""

    def __init__(self, rows=None):
        self.calls = []
        self._rows = list(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        cur = _FakeCursor()
        if self._rows:
            cur.fetchone = lambda: self._rows.pop(0)  # noqa: B023
        return cur


def _insert(conn, table):
    return next((c for c in conn.calls if f"INTO {table}" in c[0]), None)


# ─── source map / dedup key ─────────────────────────────────────────────────


class TestSourceMap:
    def test_all_sources_have_distinct_columns_and_prefixes(self):
        cols = [v[0] for v in _SOURCE_MAP.values()]
        prefixes = [v[1] for v in _SOURCE_MAP.values()]
        assert len(set(cols)) == len(cols)
        assert len(set(prefixes)) == len(prefixes)

    def test_garmin_is_the_default_for_unknown(self):
        assert _source_column("nonesuch") == "garmin_activity_id"
        assert _source_prefix("nonesuch") == "fit:"

    def test_known_sources_map_as_designed(self):
        assert _source_column("coros") == "coros_label_id"
        assert _source_column("wahoo") == "wahoo_workout_id"
        assert _source_column("polar") == "polar_exercise_id"
        assert _source_column("strava") == "strava_activity_id"


class TestFitDedupId:
    def test_default_prefix_unchanged(self):
        assert _fit_dedup_id(b"abc").startswith("fit:")

    def test_prefix_is_parameterized(self):
        assert _fit_dedup_id(b"abc", "coros-file:").startswith("coros-file:")

    def test_same_bytes_same_hash_across_prefixes(self):
        a = _fit_dedup_id(b"abc", "fit:")
        b = _fit_dedup_id(b"abc", "coros-file:")
        assert a.split(":", 1)[1] == b.split(":", 1)[1]


# ─── cardio insert ──────────────────────────────────────────────────────────


class TestBulkInsertCardio:
    def test_default_source_writes_garmin_column(self):
        conn = _FakeConn()
        _bulk_insert_cardio(conn, {"date": "2026-06-01"}, uid=3, gid="fit:x")
        sql, params = _insert(conn, "cardio_log")
        assert "garmin_activity_id" in sql
        assert "fit:x" in params

    def test_coros_writes_coros_column_only(self):
        conn = _FakeConn()
        _bulk_insert_cardio(conn, {"date": "2026-06-01"}, uid=3,
                            gid="coros-file:x", source="coros")
        sql, _ = _insert(conn, "cardio_log")
        assert "coros_label_id" in sql
        assert "garmin_activity_id" not in sql

    def test_provider_raw_row_tagged_with_source(self):
        # The corroboration row should carry the true source, not the parser's
        # garmin default — so a COROS indoor ride reads as COROS downstream.
        conn = _FakeConn()
        data = {
            "date": "2026-06-01",
            "_provider_raw": {
                "provider": "garmin",
                "observed_at": "2026-06-01",
                "bucket": 1,
                "canonical_ref": "D-006",
                "payload": {"indoor_machine": "Cycling trainer"},
            },
        }
        _bulk_insert_cardio(conn, data, uid=3, gid="coros-file:x", source="coros")
        sql, params = _insert(conn, "provider_raw_record")
        assert params[1] == "coros"          # provider tag overridden
        assert params[3] == "coros-file:x"   # external_id == the dedup key
        assert json.loads(params[5])["indoor_machine"] == "Cycling trainer"


# ─── strength insert ────────────────────────────────────────────────────────


class TestBulkInsertStrength:
    def test_source_selects_column(self, monkeypatch):
        monkeypatch.setattr(g, "apply_session_outcome", lambda *a, **k: {
            "movement_pattern": "Squat", "outcome": "hit",
            "next_weight": 100, "next_sets": 3, "next_reps": 5, "next_duration": None,
        })
        monkeypatch.setattr(g, "calculate_1rm", lambda w, r: 120)
        conn = _FakeConn()
        rows = [{"date": "2026-06-01", "exercise": "Back Squat",
                 "sets": [{"reps": 5, "weight_kg": 100}]}]
        _bulk_insert_strength(conn, rows, uid=3, gid="polar-file:y", source="polar")
        sql, params = _insert(conn, "training_log")
        assert "polar_exercise_id" in sql
        assert "garmin_activity_id" not in sql
        assert "polar-file:y" in params


# ─── dedup ──────────────────────────────────────────────────────────────────


class TestAlreadyImported:
    def test_checks_source_column(self, monkeypatch):
        monkeypatch.setattr(g, "current_user_id", lambda: 3)
        conn = _FakeConn()
        _already_imported(conn, "coros-file:x", source="coros")
        # First (and here only) query is cardio_log on the coros column.
        assert "coros_label_id" in conn.calls[0][0]
        assert "cardio_log" in conn.calls[0][0]

    def test_hit_in_cardio_short_circuits(self, monkeypatch):
        monkeypatch.setattr(g, "current_user_id", lambda: 3)
        conn = _FakeConn(rows=[{"id": 9}])
        assert _already_imported(conn, "fit:x") is True
        assert len(conn.calls) == 1  # no training_log query needed

    def test_falls_through_to_training_log(self, monkeypatch):
        monkeypatch.setattr(g, "current_user_id", lambda: 3)
        conn = _FakeConn()  # cardio miss → training_log queried
        _already_imported(conn, "wahoo-file:x", source="wahoo")
        tables = [c[0] for c in conn.calls]
        assert any("cardio_log" in s for s in tables)
        assert any("training_log" in s and "wahoo_workout_id" in s for s in tables)

    def test_strava_skips_training_log(self, monkeypatch):
        monkeypatch.setattr(g, "current_user_id", lambda: 3)
        conn = _FakeConn()  # cardio miss; strava has no training_log column
        assert _already_imported(conn, "strava-file:x", source="strava") is False
        assert len(conn.calls) == 1
        assert "cardio_log" in conn.calls[0][0]
