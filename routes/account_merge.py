"""Account merge — collapse a duplicate account into a survivor.

Resolves the duplicate-account situation the OAuth sign-in design can create
(two providers signed up separately → two accounts). See
aidstation-sources/designs/Account_Merge_Design_v1.md.

DESTRUCTIVE and feature-flagged OFF (ACCOUNT_MERGE_ENABLED). The engine
re-points every foreign key to users(id) from `drop` → `keep` inside one
transaction, resolving unique-collisions survivor-wins, then deletes `drop`.

VERIFY-OWED (Rule #14): the information_schema discovery, SAVEPOINT /
ROLLBACK TO SAVEPOINT semantics, and unique-violation detection are PG-specific
and MUST be exercised against a throwaway Postgres with two seeded accounts
before the flag is enabled. The unit tests cover orchestration branching, not
SQL-dialect correctness.
"""
from __future__ import annotations

import os
import re
from typing import Any

# Identifier guard for the table/column names we interpolate into DDL/DML.
# They come only from information_schema (never user input), but we assert the
# shape anyway so a malformed catalog row can never become injection.
_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def merge_enabled() -> bool:
    """Master gate. OFF by default — account merge is destructive and must be
    explicitly enabled (and live-verified per the design §7) before use."""
    return os.environ.get('ACCOUNT_MERGE_ENABLED', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


# ── Entry-point staging (design §6) ──────────────────────────────────────────
# The OAuth-into-the-other-account flow proves control of the duplicate ("drop")
# account: a logged-in athlete (the survivor / "keep") runs a provider OAuth
# with intent=merge; if that provider identity resolves to a DIFFERENT account,
# the callback stages that account's id here and bounces to the confirm screen.
# Keep is always the live session — never stored — so a stale value can't
# redirect the merge at the destructive `execute` step.
_SESSION_DROP_KEY = 'pending_merge_drop_id'


def stage_merge(session: Any, drop_id: int) -> None:
    session[_SESSION_DROP_KEY] = int(drop_id)


def staged_drop_id(session: Any) -> Any:
    return session.get(_SESSION_DROP_KEY)


def clear_staged_merge(session: Any) -> None:
    session.pop(_SESSION_DROP_KEY, None)


def account_label(db: Any, user_id: int) -> Any:
    """`{username, email, has_password}` for the confirm screen, or None."""
    row = db.execute(
        "SELECT username, email, COALESCE(password_hash, '') <> '' AS has_password "
        "FROM users WHERE id = ?", (user_id,),
    ).fetchone()
    if not row:
        return None
    return {'username': row['username'], 'email': row['email'],
            'has_password': bool(row['has_password'])}


def user_fk_columns(db: Any) -> list[tuple[str, str]]:
    """Every (table, column) that is a FOREIGN KEY to users(id), discovered
    dynamically (design decision #2). Catches ownership columns that aren't
    named `user_id` (gym_profiles.created_by_user_id, admin_audit.actor_user_id,
    …) so the final DELETE users can't orphan-fail. Excludes the users table
    itself (handled separately)."""
    rows = db.execute(
        "SELECT tc.table_name AS t, kcu.column_name AS c "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        " AND tc.table_schema = kcu.table_schema "
        "JOIN information_schema.constraint_column_usage ccu "
        "  ON tc.constraint_name = ccu.constraint_name "
        " AND tc.table_schema = ccu.table_schema "
        "WHERE tc.constraint_type = 'FOREIGN KEY' "
        "  AND tc.table_schema = 'public' "
        "  AND ccu.table_name = 'users' AND ccu.column_name = 'id' "
        "  AND tc.table_name <> 'users' "
        "ORDER BY tc.table_name, kcu.column_name"
    ).fetchall()
    out = []
    for r in rows:
        t, c = r['t'], r['c']
        if not _IDENT.match(t) or not _IDENT.match(c):
            raise ValueError(f'Unsafe identifier from catalog: {t!r}.{c!r}')
        out.append((t, c))
    return out


def _is_unique_violation(exc: Exception) -> bool:
    """True for a Postgres unique-constraint violation (SQLSTATE 23505), across
    the psycopg2 exception shapes and a defensive message fallback."""
    code = getattr(exc, 'pgcode', None)
    if code is None:
        diag = getattr(exc, 'diag', None)
        code = getattr(diag, 'sqlstate', None)
    if code == '23505':
        return True
    msg = str(exc).lower()
    return 'unique' in msg or 'duplicate key' in msg


def merge_accounts(db: Any, keep_id: int, drop_id: int) -> dict:
    """Merge `drop_id` into `keep_id` and delete `drop_id`. Returns a summary
    {repointed: {table.col: n}, collided: {table.col: n}} for the audit log.

    All-or-nothing (design decision #4): re-points each FK-to-users column in a
    SAVEPOINT; a unique-violation falls back to survivor-wins (delete drop's
    rows for that table); ANY other error rolls the whole merge back and
    re-raises, leaving both accounts intact. Caller owns higher-level guards
    (proof of control of both accounts, confirmation, re-auth — design §6).
    """
    if not merge_enabled():
        raise RuntimeError('account merge is disabled (ACCOUNT_MERGE_ENABLED)')
    if keep_id == drop_id:
        raise ValueError('cannot merge an account into itself')
    for uid in (keep_id, drop_id):
        if db.execute('SELECT 1 FROM users WHERE id = ?', (uid,)).fetchone() is None:
            raise ValueError(f'no such user: {uid}')

    summary: dict[str, dict[str, int]] = {'repointed': {}, 'collided': {}}
    try:
        for i, (table, col) in enumerate(user_fk_columns(db)):
            sp = f'acct_merge_sp_{i}'
            key = f'{table}.{col}'
            db.execute(f'SAVEPOINT {sp}')
            try:
                cur = db.execute(
                    f'UPDATE {table} SET {col} = ? WHERE {col} = ?',
                    (keep_id, drop_id),
                )
                db.execute(f'RELEASE SAVEPOINT {sp}')
                summary['repointed'][key] = cur.rowcount or 0
            except Exception as exc:  # noqa: BLE001
                db.execute(f'ROLLBACK TO SAVEPOINT {sp}')
                if not _is_unique_violation(exc):
                    raise  # real fault → outer rollback, nothing committed
                # Survivor wins this table (design decision #3 / §5).
                cur = db.execute(
                    f'DELETE FROM {table} WHERE {col} = ?', (drop_id,)
                )
                summary['collided'][key] = cur.rowcount or 0

        cur = db.execute('DELETE FROM users WHERE id = ?', (drop_id,))
        summary['dropped_user'] = (cur.rowcount or 0)  # type: ignore[assignment]
        db.commit()
    except Exception:
        db.rollback()
        raise

    print(f'[account-merge] keep={keep_id} drop={drop_id} '  # noqa: T201 — Rule #15
          f'repointed={summary["repointed"]} collided={summary["collided"]}')
    return summary
