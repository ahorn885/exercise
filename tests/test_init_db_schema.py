"""Guards on `init_db.PG_SCHEMA` integrity.

`init_postgres` executes the schema by `PG_SCHEMA.split(';')` — a naive split
that does not understand SQL line comments. A ';' inside a `-- comment` therefore
breaks the comment mid-line into a non-statement fragment, which raises a syntax
error and (pre-fix) aborted the whole init silently — blocking every schema and
migration change from that point on (the #681 §4 prod incident, 2026-06-19, where
provider_value_map / provider_raw_record / cardio_log.discipline_id never reached
prod). These tests fail loudly if a semicolon ever sneaks back into a comment.
"""

import init_db

_DDL_KEYWORDS = ('CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'COMMENT', 'DO')


def _fragments():
    return [s.strip() for s in init_db.PG_SCHEMA.split(';') if s.strip()]


def test_pg_schema_has_no_mid_comment_semicolon_split():
    """Every split fragment must begin with a real statement once comment-only
    lines are stripped. A fragment whose first non-comment line is bare prose is
    the signature of a ';' inside a comment having split it."""
    malformed = []
    for frag in _fragments():
        non_comment = [
            ln for ln in frag.splitlines()
            if ln.strip() and not ln.strip().startswith('--')
        ]
        if non_comment and not non_comment[0].strip().upper().startswith(_DDL_KEYWORDS + ('(',)):
            malformed.append(non_comment[0].strip())
    assert not malformed, (
        'PG_SCHEMA.split(\';\') produced non-statement fragment(s) — a semicolon '
        'is almost certainly inside a SQL comment: ' + repr(malformed)
    )


def test_provider_tables_present_in_schema():
    """The Slice-1 provider tables must survive the split as their own CREATE
    fragments (they sit right after the comment that triggered the incident)."""
    frags = _fragments()
    assert any('CREATE TABLE IF NOT EXISTS provider_value_map' in f for f in frags)
    assert any('CREATE TABLE IF NOT EXISTS provider_raw_record' in f for f in frags)
