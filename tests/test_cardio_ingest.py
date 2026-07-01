"""Real-database cardio-ingest tests (#754/T-5.7).

Every other cardio-ingest test (`tests/test_garmin_bulk_source.py`,
`tests/test_wahoo_ingest.py`, ...) exercises `_bulk_insert_cardio` /
`_record_provider_raw_cardio` against a fake connection that just records the
SQL string + params. That catches wiring bugs but not real-SQL bugs: a bad
type cast, a missing column, an `ON CONFLICT` arbiter that doesn't match the
table's actual constraint. #752 was exactly that class (an empty
`observed_at` string blew up as `psycopg2.errors.InvalidDatetimeFormat`
against a real Postgres, invisible to the fake-DB suite) — fixed, but nothing
guards the class from recurring.

This file runs the real writer functions against a real (scratch) Postgres
database, bootstrapped via `init_db.init_postgres()` exactly like prod. It is
skipped by default (`requires_real_postgres`, see `tests/conftest.py`) so
`pytest tests/` stays $0 — set `TEST_DATABASE_URL` to a throwaway Postgres
database to run it:

    createdb aidstation_test
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aidstation_test \\
        /tmp/venv/bin/python -m pytest tests/test_cardio_ingest.py -q

Covers the plan's stated scope: `_bulk_insert_cardio` + dedup + provider_raw
across all sources.
"""

from __future__ import annotations

import os

import psycopg2
import pytest
from flask import Flask, session

from tests.conftest import TEST_DATABASE_URL_ENV, requires_real_postgres

pytestmark = requires_real_postgres

# Sources that have a partial UNIQUE index on (user_id, <col>) — see
# init_db.py's PR3-follow-up migrations. `garmin` has no such index (the
# legacy Connect-sync path never got one); `_already_imported` is its only
# dedup guard, checked by the caller before insert, not by a DB constraint.
_INDEXED_SOURCES = ["coros", "wahoo", "polar", "strava"]


@pytest.fixture(scope="session")
def _schema_bootstrapped():
    """Bootstrap the scratch database's schema once per test session.

    Mirrors the next-session recipe in the T-5.4/5/6 handoff: point
    `init_db.DATABASE_URL` at the scratch Postgres and call
    `init_db.init_postgres()`, the same bootstrap prod runs on every deploy.
    """
    url = os.environ[TEST_DATABASE_URL_ENV]
    import database
    import init_db

    init_db.DATABASE_URL = url
    database.DATABASE_URL = url
    init_db.init_postgres()
    return url


@pytest.fixture
def db(_schema_bootstrapped):
    """One real Postgres connection per test, wrapped in the app's own
    `_PgConn` compat layer (so `?`-placeholder SQL + `.lastrowid` behave
    exactly like they do against prod), with a throwaway user row. Never
    committed — rolled back at teardown so tests don't leak state into each
    other or require manual truncation."""
    from database import _PgConn, _connect

    conn = _PgConn(_connect())
    uid = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id",
        (f"cardio-ingest-test-{id(conn)}", "x"),
    ).lastrowid
    try:
        yield conn, uid
    finally:
        conn.rollback()
        conn.close()


def _cardio_data(**overrides) -> dict:
    data = {
        "date": "2026-07-01",
        "activity": "run",
        "activity_name": "Morning run",
        "duration_min": 45.0,
        "distance_mi": 6.2,
        "avg_hr": 148,
        "_provider_raw": {
            "provider": "garmin",
            "observed_at": "2026-07-01T08:00:00Z",
            "bucket": 2,
            "canonical_ref": "D-006",
            "payload": {"indoor_machine": None},
        },
    }
    data.update(overrides)
    return data


class TestBulkInsertCardioAcrossSources:
    """The plan's own T-5.7 scope: `_bulk_insert_cardio` + `provider_raw`
    across all sources, against real Postgres."""

    @pytest.mark.parametrize("source,column", [
        ("garmin", "garmin_activity_id"),
        ("coros", "coros_label_id"),
        ("wahoo", "wahoo_workout_id"),
        ("polar", "polar_exercise_id"),
        ("strava", "strava_activity_id"),
    ])
    def test_writes_gid_to_source_column(self, db, source, column):
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        gid = f"{source}:abc123"
        rec_id = _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid, source=source)

        row = conn.execute(
            f"SELECT {column}, user_id, date FROM cardio_log WHERE id = ?", (rec_id,)
        ).fetchone()
        assert row[column] == gid
        assert row["user_id"] == uid
        assert row["date"] == "2026-07-01"

    @pytest.mark.parametrize("source", ["garmin", "coros", "wahoo", "polar", "strava"])
    def test_provider_raw_record_tagged_with_source(self, db, source):
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        gid = f"{source}:raw1"
        _bulk_insert_cardio(
            conn,
            _cardio_data(_provider_raw={
                "provider": "garmin",  # deliberately mismatched: real source wins
                "observed_at": "2026-07-01T08:00:00Z",
                "bucket": 2, "canonical_ref": "D-006",
                "payload": {"indoor_machine": "Treadmill"},
            }),
            uid=uid, gid=gid, source=source,
        )

        raw = conn.execute(
            "SELECT provider, external_id, raw_payload, bucket, canonical_ref "
            "FROM provider_raw_record WHERE user_id = ? AND external_id = ?",
            (uid, gid),
        ).fetchone()
        assert raw is not None
        assert raw["provider"] == source
        assert raw["bucket"] == 2
        assert raw["canonical_ref"] == "D-006"
        assert raw["raw_payload"]["indoor_machine"] == "Treadmill"


class TestEmptyObservedAtCoercesNull:
    """The #752 regression class: a FIT whose session timestamp didn't parse
    yields `observed_at=''`, which is not a valid Postgres TIMESTAMP literal.
    The fake-DB suite can't catch this (it never sends the param to a real
    server); this does."""

    def test_blank_observed_at_stores_null_not_raise(self, db):
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        gid = "fit:blank-ts"
        rec_id = _bulk_insert_cardio(
            conn,
            _cardio_data(_provider_raw={
                "provider": "garmin", "observed_at": "",
                "bucket": 1, "canonical_ref": None, "payload": {},
            }),
            uid=uid, gid=gid,
        )
        assert rec_id is not None

        raw = conn.execute(
            "SELECT observed_at FROM provider_raw_record WHERE user_id = ? AND external_id = ?",
            (uid, gid),
        ).fetchone()
        assert raw["observed_at"] is None


class TestProviderRawUpsertOnConflict:
    """`provider_raw_record`'s `ON CONFLICT (user_id, provider, data_type,
    external_id) DO UPDATE` is the arbiter-mismatch risk the plan calls out
    by name — this proves the real unique constraint the arbiter targets
    actually matches."""

    def test_second_write_same_external_id_updates_not_duplicates(self, db):
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        gid = "fit:reimport"
        _bulk_insert_cardio(
            conn,
            _cardio_data(_provider_raw={
                "provider": "garmin", "observed_at": "2026-07-01T08:00:00Z",
                "bucket": 1, "canonical_ref": "D-001",
                "payload": {"indoor_machine": "Treadmill"},
            }),
            uid=uid, gid=gid,
        )
        _bulk_insert_cardio(
            conn,
            _cardio_data(_provider_raw={
                "provider": "garmin", "observed_at": "2026-07-01T08:05:00Z",
                "bucket": 1, "canonical_ref": "D-001",
                "payload": {"indoor_machine": "Bike trainer"},
            }),
            uid=uid, gid=gid,
        )

        rows = conn.execute(
            "SELECT raw_payload FROM provider_raw_record WHERE user_id = ? AND external_id = ?",
            (uid, gid),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["raw_payload"]["indoor_machine"] == "Bike trainer"


class TestDedupUniqueIndexEnforced:
    """coros/wahoo/polar/strava each get a partial UNIQUE index on
    `(user_id, <source column>)` (init_db.py's PR3-follow-up migrations) —
    the real dedup guard for a provider's live/webhook path. Confirms the
    index actually exists and is wired to the right column per source,
    against the real bootstrapped schema."""

    @pytest.mark.parametrize("source", _INDEXED_SOURCES)
    def test_duplicate_gid_same_user_raises_unique_violation(self, db, source):
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        gid = f"{source}:dup"
        _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid, source=source)

        with pytest.raises(psycopg2.errors.UniqueViolation):
            _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid, source=source)

    def test_duplicate_gid_different_user_does_not_collide(self, db):
        from database import _connect, _PgConn
        from routes.garmin import _bulk_insert_cardio

        conn, uid = db
        other = _PgConn(_connect())
        try:
            other_uid = other.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id",
                (f"cardio-ingest-test-other-{id(other)}", "x"),
            ).lastrowid
            gid = "wahoo:shared-across-users"
            _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid, source="wahoo")
            # Different connection/transaction + different user: the partial
            # unique index is scoped to (user_id, col), so this must succeed.
            rec_id = _bulk_insert_cardio(other, _cardio_data(), uid=other_uid, gid=gid, source="wahoo")
            assert rec_id is not None
        finally:
            other.rollback()
            other.close()


class TestAlreadyImported:
    """`_already_imported` is the caller-side dedup guard for sources with
    no DB-level unique index (garmin) and the pre-insert check every ingest
    route makes before calling `_bulk_insert_cardio`."""

    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test"
        app.config["TESTING"] = True
        return app

    def test_detects_existing_activity_for_the_authenticated_user(self, db, app):
        from routes.garmin import _already_imported, _bulk_insert_cardio

        conn, uid = db
        gid = "fit:seen-already"
        _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid)

        with app.test_request_context("/"):
            session["user_id"] = uid
            assert _already_imported(conn, gid) is True
            assert _already_imported(conn, "fit:never-seen") is False

    def test_scoped_to_the_authenticated_user_only(self, db, app):
        from database import _connect, _PgConn
        from routes.garmin import _already_imported, _bulk_insert_cardio

        conn, uid = db
        other = _PgConn(_connect())
        try:
            other_uid = other.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id",
                (f"cardio-ingest-test-other-{id(other)}", "x"),
            ).lastrowid
            gid = "fit:mine-not-yours"
            _bulk_insert_cardio(conn, _cardio_data(), uid=uid, gid=gid)

            with app.test_request_context("/"):
                session["user_id"] = other_uid
                assert _already_imported(other, gid) is False
        finally:
            other.rollback()
            other.close()
