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
from datetime import datetime, timedelta, timezone

import pytest

import routes.garmin as g
from routes.garmin import (
    _SOURCE_MAP,
    _already_imported,
    _bulk_insert_cardio,
    _bulk_insert_strength,
    _coarse_sport,
    _fit_dedup_id,
    _normalize_started_at,
    _source_column,
    _source_prefix,
    cluster_activity,
)


class _FakeCursor:
    lastrowid = 1

    def fetchone(self):
        return None

    def fetchall(self):
        return []


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


# ─── started_at — cross-source fingerprint input (#196 P3 Slice 1) ───────────


class TestNormalizeStartedAt:
    """The UTC start instant clustering will fingerprint on (Slice 2). The
    normalizer must collapse every provider's start representation to one
    naive-UTC datetime so a Wahoo ride and its Strava auto-forward compare equal."""

    def test_utc_z_string_to_naive_utc(self):
        # Wahoo-style ISO-8601 with a Z designator (observed_at fallback).
        assert _normalize_started_at(
            {"_provider_raw": {"observed_at": "2026-06-22T06:28:56Z"}}
        ) == datetime(2026, 6, 22, 6, 28, 56)

    def test_fractional_seconds_z(self):
        assert _normalize_started_at(
            {"_provider_raw": {"observed_at": "2026-06-22T06:28:56.000Z"}}
        ) == datetime(2026, 6, 22, 6, 28, 56)

    def test_numeric_offset_converted_to_utc(self):
        # RWGPS departed_at carries a real offset → shift to UTC.
        assert _normalize_started_at(
            {"_provider_raw": {"observed_at": "2026-06-22T07:00:00-08:00"}}
        ) == datetime(2026, 6, 22, 15, 0, 0)

    def test_date_only_lands_at_midnight(self):
        # Manual FIT/TCX/GPX observed_at is date-only → 00:00 UTC.
        assert _normalize_started_at(
            {"_provider_raw": {"observed_at": "2026-06-22"}}
        ) == datetime(2026, 6, 22, 0, 0, 0)

    def test_explicit_started_at_wins_over_observed_at(self):
        # Strava passes its true-UTC start_date as started_at; observed_at is the
        # local start_date_local. The explicit UTC value must win.
        d = {"started_at": "2026-06-22T06:28:56Z",
             "_provider_raw": {"observed_at": "2026-06-22T01:28:56Z"}}
        assert _normalize_started_at(d) == datetime(2026, 6, 22, 6, 28, 56)

    def test_aware_datetime_object_normalized(self):
        aware = datetime(2026, 6, 22, 7, 0, tzinfo=timezone(timedelta(hours=-8)))
        assert _normalize_started_at({"started_at": aware}) == datetime(2026, 6, 22, 15, 0)

    def test_absent_is_none(self):
        assert _normalize_started_at({}) is None
        assert _normalize_started_at({"_provider_raw": {"observed_at": None}}) is None
        assert _normalize_started_at({"_provider_raw": {"observed_at": ""}}) is None

    def test_unparseable_is_none_not_raise(self):
        # A bad start must degrade to NULL, never break the import (Rule #15).
        assert _normalize_started_at(
            {"_provider_raw": {"observed_at": "not-a-date"}}
        ) is None


class TestCardioInsertStartedAt:
    def test_started_at_column_and_resolved_value_in_insert(self):
        conn = _FakeConn()
        _bulk_insert_cardio(
            conn,
            {"date": "2026-06-22",
             "_provider_raw": {"observed_at": "2026-06-22T06:28:56Z"}},
            uid=3, gid="wahoo-file:x", source="wahoo")
        sql, params = _insert(conn, "cardio_log")
        assert "started_at" in sql
        assert datetime(2026, 6, 22, 6, 28, 56) in params

    def test_started_at_null_does_not_break_insert(self):
        conn = _FakeConn()
        rec_id = _bulk_insert_cardio(conn, {"date": "2026-06-22"}, uid=3, gid="fit:x")
        sql, _ = _insert(conn, "cardio_log")
        assert "started_at" in sql
        assert rec_id == 1  # inserted cleanly despite no resolvable start


# ─── cross-source clustering (#196 P3 Slice 2) ───────────────────────────────


class _ClusterConn:
    """Fake DB for cluster_activity: queued rows feed the activity_clusters
    candidate SELECT; INSERT ... RETURNING yields `new_cluster_id` via lastrowid.
    Records every (sql, params) so a test can assert which writes happened."""

    def __init__(self, candidates=None, new_cluster_id=99):
        self.calls = []
        self._candidates = list(candidates or [])
        self._new_id = new_cluster_id

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        cur = _FakeCursor()
        if "FROM activity_clusters" in sql:
            rows = self._candidates
            cur.fetchall = lambda: rows  # noqa: B023
        if "INTO activity_clusters" in sql:
            cur.lastrowid = self._new_id
        return cur

    def did(self, fragment):
        return any(fragment in c[0] for c in self.calls)

    def params_for(self, fragment):
        return next((p for s, p in self.calls if fragment in s), None)


def _cluster_row(**over):
    row = {"id": 7, "sport_class": "cycling",
           "started_at": datetime(2026, 6, 22, 6, 28, 50),
           "duration_min": 30.0, "distance_mi": 0.0}
    row.update(over)
    return row


class TestCoarseSport:
    """The loose coarse-sport family resolver — Andy: "some apps may not have
    categories which match perfectly." Canonical discipline → family first, then
    the resolver-less provider vocab folded onto that same namespace."""

    def test_canonical_discipline_wins(self):
        assert _coarse_sport({"discipline_id": "D-006"}) == "cycling"   # any cycling D-id
        assert _coarse_sport({"discipline_id": "D-001"}) == "running"   # Trail Running
        assert _coarse_sport({"discipline_id": "D-004"}) == "swimming"
        assert _coarse_sport({"discipline_id": "D-003"}) == "hiking"

    def test_provider_freetext_folds_to_family(self):
        # Polar/COROS singular vocab (no discipline_id) maps onto the same family
        # the resolver-backed providers produce, so 'cycle' clusters with 'cycling'.
        assert _coarse_sport({"activity": "cycle"}) == "cycling"
        assert _coarse_sport({"activity": "run"}) == "running"
        assert _coarse_sport({"activity": "Trail Run"}) == "running"
        assert _coarse_sport({"activity": "swim"}) == "swimming"
        assert _coarse_sport({"activity": "hike"}) == "hiking"

    def test_discipline_takes_priority_over_activity(self):
        assert _coarse_sport({"discipline_id": "D-006", "activity": "run"}) == "cycling"

    def test_unmapped_passes_through_and_empty_is_other(self):
        assert _coarse_sport({"activity": "pickleball"}) == "pickleball"
        assert _coarse_sport({}) == "other"
        # A fine-only discipline with no coarse home (climbing) collapses to the
        # 'other' wildcard rather than blocking a match.
        assert _coarse_sport({"discipline_id": "D-012"}) == "other"


class TestClusterActivity:
    REPRO_START = datetime(2026, 6, 22, 6, 28, 56)

    def test_no_candidates_opens_new_cluster(self):
        conn = _ClusterConn(candidates=[], new_cluster_id=42)
        cid = cluster_activity(
            conn, uid=1, cardio_id=73,
            data={"activity": "cycling", "discipline_id": "D-006",
                  "duration_min": 30.0, "distance_mi": 0.0},
            started_at=self.REPRO_START)
        assert cid == 42
        assert conn.did("SELECT pg_advisory_xact_lock")
        assert conn.did("INTO activity_clusters")
        assert conn.params_for("INTO activity_clusters")[1] == "cycling"  # sport_class
        assert conn.params_for("UPDATE cardio_log SET cluster_id") == (42, 73)

    def test_indoor_dup_attaches_to_existing_cluster(self):
        # The repro: row 74 (Strava) lands ~6s after row 73 (Wahoo), same indoor
        # ride — duration corroborates, distance is 0 on both (skipped).
        conn = _ClusterConn(candidates=[_cluster_row(id=7, duration_min=30.0)])
        cid = cluster_activity(
            conn, uid=1, cardio_id=74,
            data={"activity": "cycling", "discipline_id": "D-006",
                  "duration_min": 30.2, "distance_mi": 0.0},
            started_at=self.REPRO_START)
        assert cid == 7
        assert not conn.did("INTO activity_clusters")          # attached, not forked
        assert conn.params_for("UPDATE cardio_log SET cluster_id") == (7, 74)
        assert conn.did("UPDATE activity_clusters SET updated_at")

    def test_cross_provider_label_mismatch_still_clusters(self):
        # COROS 'cycle' (no discipline_id) must attach to a Strava-opened
        # 'cycling' cluster — the whole point of the loose sport match.
        conn = _ClusterConn(candidates=[_cluster_row(distance_mi=12.0, duration_min=45.0)])
        cid = cluster_activity(
            conn, uid=1, cardio_id=80,
            data={"activity": "cycle", "duration_min": 45.0, "distance_mi": 12.1},
            started_at=self.REPRO_START)
        assert cid == 7
        assert not conn.did("INTO activity_clusters")

    def test_duration_disagreement_opens_new(self):
        # Same time + sport, but 60 min vs the cluster's 30 → distinct activities.
        conn = _ClusterConn(candidates=[_cluster_row(duration_min=30.0)], new_cluster_id=88)
        cid = cluster_activity(
            conn, uid=1, cardio_id=81,
            data={"activity": "cycling", "discipline_id": "D-006",
                  "duration_min": 60.0, "distance_mi": 0.0},
            started_at=self.REPRO_START)
        assert cid == 88
        assert conn.did("INTO activity_clusters")

    def test_known_sport_mismatch_opens_new(self):
        # A run and a ride that share start + duration + distance must NOT merge.
        conn = _ClusterConn(candidates=[_cluster_row(distance_mi=3.0, duration_min=25.0)],
                            new_cluster_id=77)
        cid = cluster_activity(
            conn, uid=1, cardio_id=82,
            data={"activity": "running", "discipline_id": "D-001",
                  "duration_min": 25.0, "distance_mi": 3.0},
            started_at=self.REPRO_START)
        assert cid == 77
        assert conn.did("INTO activity_clusters")

    def test_start_outside_window_opens_new(self):
        # 9 min apart (> ±5 min) → not the same activity even if everything else
        # lines up. (The candidate SQL would also exclude it; belt and suspenders.)
        conn = _ClusterConn(candidates=[_cluster_row(duration_min=30.0)], new_cluster_id=55)
        cid = cluster_activity(
            conn, uid=1, cardio_id=83,
            data={"activity": "cycling", "discipline_id": "D-006",
                  "duration_min": 30.0, "distance_mi": 0.0},
            started_at=datetime(2026, 6, 22, 6, 38, 0))
        assert cid == 55
        assert conn.did("INTO activity_clusters")

    def test_null_start_is_left_unclustered(self):
        conn = _ClusterConn()
        cid = cluster_activity(conn, uid=1, cardio_id=84,
                               data={"activity": "cycling"}, started_at=None)
        assert cid is None
        assert not conn.did("SELECT pg_advisory_xact_lock")  # bails before any write
        assert not conn.did("INTO activity_clusters")

    def test_bulk_insert_cardio_invokes_clusterer(self):
        # End-to-end: a resolvable start drives _bulk_insert_cardio through the
        # clusterer (lock + cluster write), every provider path included.
        conn = _FakeConn()
        _bulk_insert_cardio(
            conn,
            {"date": "2026-06-22", "activity": "cycling", "discipline_id": "D-006",
             "duration_min": 30.0, "distance_mi": 0.0,
             "_provider_raw": {"observed_at": "2026-06-22T06:28:56Z"}},
            uid=1, gid="wahoo:x", source="wahoo")
        assert any("pg_advisory_xact_lock" in c[0] for c in conn.calls)
        assert any("INTO activity_clusters" in c[0] for c in conn.calls)
