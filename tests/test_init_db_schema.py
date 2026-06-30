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


def test_pg_schema_no_semicolon_in_line_comments():
    """Direct lint for the #681 §4 root cause: a ';' inside a `-- line comment`.

    `init_postgres` splits the schema on ';' (a char-based split that does not
    understand SQL), so any ';' inside a comment breaks that comment mid-line
    into a bare-prose fragment and raises a syntax error. The fragment-shape
    check above catches the *downstream* symptom; this one forbids the cause
    outright and points straight at the offending line, so the splitter staying
    char-based (the #747 residual) can never silently re-break.

    If a future statement legitimately needs a ';' that is not a terminator,
    swap `init_postgres` to a SQL-aware splitter and relax this lint — don't
    smuggle the ';' into a comment."""
    offenders = []
    for lineno, line in enumerate(init_db.PG_SCHEMA.splitlines(), start=1):
        marker = line.find('--')
        if marker != -1 and ';' in line[marker:]:
            offenders.append(f'line {lineno}: {line.strip()!r}')
    assert not offenders, (
        "PG_SCHEMA has a ';' inside a SQL line comment — init_postgres's "
        "split(';') will break this comment into a non-statement fragment "
        '(the #681 §4 prod incident). Remove or reword the comment:\n'
        + '\n'.join(offenders)
    )


def test_health_screening_migration_present_and_idempotent():
    """Phase 0 (#246/#394/#223) — the health_screening table is a single
    `_PG_MIGRATIONS` statement (executed standalone, so the ';'-split incident
    above does not apply). It must be `IF NOT EXISTS` (re-run safe), carry no
    internal ';' (the migration runner executes one statement per entry), and
    hold the spec-required columns."""
    stmts = [s for s in init_db._PG_MIGRATIONS if isinstance(s, str)]
    matches = [s for s in stmts if 'health_screening' in s]
    assert len(matches) == 1, 'expected exactly one health_screening migration'
    stmt = matches[0]
    assert 'CREATE TABLE IF NOT EXISTS health_screening' in stmt
    assert ';' not in stmt  # one statement per entry — no split needed/allowed
    for col in ('flags JSONB', 'details JSONB', 'details_optin BOOLEAN',
                'acknowledged', 'acknowledged_at', 'last_assessed_at',
                'reassessment_due_at'):
        assert col in stmt, f'missing column: {col}'
