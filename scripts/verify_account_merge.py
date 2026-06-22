#!/usr/bin/env python
"""Live-PG verification for the account-merge engine (#857 / design §7).

Runs against a THROWAWAY Postgres (the CI service in
.github/workflows/account-merge-verify.yml, or a local Docker) — NEVER prod.
Seeds two accounts with a re-point case + a singleton-collision case, runs the
real `account_merge.merge_accounts`, and asserts the outcome. Exit 0 = PASS,
1 = FAIL. This is the gate the design owes before `ACCOUNT_MERGE_ENABLED` is
ever set: it exercises the PG-specific SQL (information_schema discovery,
SAVEPOINT / ROLLBACK TO SAVEPOINT, unique-violation detection) the fake-DB unit
tests can't.

Local use:
    DATABASE_URL=postgresql://... ACCOUNT_MERGE_ENABLED=1 \
        python scripts/verify_account_merge.py
"""
from __future__ import annotations

import os
import sys
import traceback


def main() -> int:
    os.environ.setdefault('ACCOUNT_MERGE_ENABLED', '1')
    from database import _PgConn, _connect
    from routes import account_merge as am

    db = _PgConn(_connect())

    # Two fresh accounts.
    keep = db.execute(
        "INSERT INTO users (username, password_hash) "
        "VALUES ('merge_keep_test', 'x') RETURNING id").fetchone()['id']
    drop = db.execute(
        "INSERT INTO users (username, password_hash) "
        "VALUES ('merge_drop_test', 'x') RETURNING id").fetchone()['id']

    # Re-point case: drop owns a provider identity, keep doesn't → moves to keep.
    db.execute("INSERT INTO provider_identity (user_id, provider, provider_user_id) "
               "VALUES (?, 'strava', '999000999')", (drop,))
    # Singleton-collision case: both hold an athlete_profile (PK is user_id) →
    # survivor (keep) is kept, drop's is deleted.
    db.execute("INSERT INTO athlete_profile (user_id) VALUES (?)", (keep,))
    db.execute("INSERT INTO athlete_profile (user_id) VALUES (?)", (drop,))
    db.commit()

    summary = am.merge_accounts(db, keep_id=keep, drop_id=drop)
    print('SUMMARY:', summary)

    ident = db.execute("SELECT user_id FROM provider_identity "
                       "WHERE provider_user_id = '999000999'").fetchone()
    prof = [r['user_id'] for r in db.execute(
        "SELECT user_id FROM athlete_profile WHERE user_id IN (?, ?)",
        (keep, drop)).fetchall()]

    checks = [
        ('drop account deleted',
         db.execute("SELECT 1 FROM users WHERE id = ?", (drop,)).fetchone() is None),
        ('provider_identity re-pointed to keep',
         ident is not None and ident['user_id'] == keep),
        ('athlete_profile collision resolved survivor-wins',
         prof == [keep]),
    ]
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print('RESULT: FAIL (exception)')
        sys.exit(1)
