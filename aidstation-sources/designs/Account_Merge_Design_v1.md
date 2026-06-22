# Account Merge Design

**Version:** 1.0
**Date:** 2026-06-21
**Status:** Draft + first slice (engine). Depends on the OAuth sign-in work (PR #843) being in `main` — merge reconciles `provider_identity` / `provider_auth` rows. Feature-flagged `ACCOUNT_MERGE_ENABLED` (OFF). DESTRUCTIVE — see §8.
**Backlog row:** deferred item from `Onboarding_OAuth_Signin_Design_v1` §10 ("two providers → two accounts").
**Cross-references:** `Onboarding_OAuth_Signin_Design_v1.md` (the duplicate-account situation this resolves; decision #5 no-silent-merge).

---

## 1. Problem

The OAuth sign-in design can create **duplicate accounts**: an athlete who signs up with Strava (account **A**), then later — logged out — "Continue with Wahoo", gets a second account **B** because we can't prove the two provider identities are the same human (and we refuse to merge on an unverified email, decision #5). Result: one person, two accounts, data split across both.

Prevention already exists (the "already have an account? log in and link" prompt → §6.2 logged-in linking). **Account merge is the cleanup tool for when prevention failed**: collapse B into A, deliberately and with proof of control of both.

---

## 2. Why it's hard (and why it's its own flagged feature)

Every per-user table is scoped by a foreign key to `users(id)` — and there are ~30 of them. A merge must re-point all of them from B → A, which surfaces:

1. **Singleton collisions.** `athlete_profile` is `PRIMARY KEY (user_id)`; `current_rx` is `UNIQUE (user_id, exercise)`. A and B each have rows that collide on re-point — you can't just move B's.
2. **Differently-named FK columns.** Ownership isn't always `user_id`: `gym_profiles.created_by_user_id` / `last_confirmed_by`, `admin_audit.actor_user_id`. Miss one and the final `DELETE users` FK-fails.
3. **Provider uniqueness.** `provider_identity`/`provider_auth` carry `UNIQUE (user_id, provider)`; if both accounts connected the same provider, re-point collides.
4. **Irreversibility.** After merge, B is gone. A wrong direction or a bad collision call has no clean undo.

This is why it ships behind a flag, OFF, as its own reviewed PR — never auto-triggered, never on an unverified-email guess.

---

## 3. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Direction | **Merge `drop` → `keep`.** The athlete is logged into `keep` (survivor); `drop` is the proven-second account that disappears. | The survivor is the session the athlete chose to keep; explicit and predictable. |
| 2 | FK discovery | **Dynamic, via `information_schema`** — find every column that is a FK to `users(id)`, regardless of name. | Robust against new tables and oddly-named ownership columns (§2.2). No fragile hardcoded list to rot. |
| 3 | Re-point vs collision | **Re-point in a per-column savepoint; on a unique-violation, survivor wins** — delete `drop`'s rows for that table. | Append-only logs (the bulk of value — activities, training log) re-point cleanly. Singleton/config collisions resolve to the survivor's data, deterministically. |
| 4 | Atomicity | **One transaction.** Any unexpected (non-unique) error → roll the whole thing back; both accounts survive intact. | A half-merged account is worse than no merge. All-or-nothing. |
| 5 | Auth to merge | **Prove control of BOTH accounts.** Logged in as `keep`; prove `drop` via OAuth into a provider that belongs to `drop`, or `drop`'s password. (Entry-point flow — next slice.) | Merge is destructive and account-spanning; it must never run on anything less than proof of both. |
| 6 | Identity rows | Re-point `provider_identity` to `keep` where the provider slot is free; on `(user_id, provider)` collision, survivor's identity wins (drop's is deleted). | Same survivor-wins policy; the athlete keeps signing in with whatever `keep` already had. |
| 7 | Scope of v1 | **Engine + tests this slice; entry-point UI next.** No row-level field-merge of singletons (survivor wins whole rows). | Ship the reviewable core first. Field-level merge (pick A's weight vs B's) is a refinement, not v1. |

---

## 4. The engine (`routes/account_merge.py`)

`merge_accounts(db, keep_id, drop_id) -> summary`:

1. Guard: `keep_id != drop_id`; both users exist; flag enabled.
2. Discover every `(table, column)` that is a FK to `users(id)` (decision #2).
3. For each, inside a SAVEPOINT: `UPDATE {table} SET {col} = keep WHERE {col} = drop`.
   - On a **unique-violation**: `ROLLBACK TO SAVEPOINT`, then `DELETE FROM {table} WHERE {col} = drop` (survivor wins, decision #3).
   - On any **other** error: re-raise → outer rollback (decision #4).
4. `DELETE FROM users WHERE id = drop` (now unreferenced).
5. `COMMIT`. Return a summary `{repointed: {table: n}, collided: {table: n}}` for the audit log (Rule #15).

Table/column names are interpolated (identifiers can't be parameterized) but come **only** from `information_schema`, never user input — no injection surface.

---

## 5. Collision policy (decision #3) — the one to scrutinize

"Survivor wins the whole table on collision" means: for a composite-unique table (e.g. `current_rx (user_id, exercise)`), if **any** of `drop`'s rows collide, the re-point statement fails and we delete **all** of `drop`'s rows for that table — including non-colliding ones. For `current_rx`/`athlete_profile` (per-user config the survivor already has) this is correct and expected. It would lose data only if there were a user-scoped table where row-by-row merge across distinct keys is desirable; none of today's tables fit that. A v2 could re-point non-colliding rows individually and delete only the conflicts. **Documented limitation, acceptable for v1.**

---

## 6. Entry point (next slice, not this one)

From account settings: "Merge another account." Athlete (logged in as `keep`) proves `drop` by OAuth into a provider linked to `drop` (or `drop`'s password). On proof, show a confirmation screen ("This permanently moves <drop>'s data into this account and deletes <drop>. Cannot be undone.") → POST runs `merge_accounts`. Gated by `ACCOUNT_MERGE_ENABLED` + a re-auth of `keep`'s password.

---

## 7. Testing

- **This slice:** fake-DB unit tests for the orchestration — self-merge guard, the FK-discovery loop re-points each discovered column, the unique-violation fallback deletes `drop`'s rows, a non-unique error aborts the whole merge (nothing deleted).
- **Verify-owed (Rule #14):** the `information_schema` queries, savepoint/`ROLLBACK TO SAVEPOINT` semantics, and unique-violation detection are PG-specific and **must be exercised against a throwaway Postgres with two seeded accounts** before the flag is enabled. The fake-DB tests cover branching, not SQL-dialect correctness.

---

## 8. Gut check

**What's right.** Dynamic FK discovery is the only maintainable way to re-point ~30 tables without a list that rots. One-transaction all-or-nothing is the right safety posture for a destructive op. Survivor-wins-on-collision is simple and predictable.

**Risks.** (1) The collision policy can drop `drop`'s non-colliding rows in composite-unique tables (§5) — fine for today's tables, revisit if that changes. (2) The engine is **untested against real PG** in this environment; it is flagged OFF and must not be enabled until §7's live test passes. (3) Irreversibility — mitigated by requiring proof of both accounts (decision #5) and an explicit, scary confirmation (§6); a future enhancement could snapshot `drop`'s rows to an audit table before deletion for a recovery window.

**Best argument against shipping now.** Duplicates are rare-to-nonexistent for a solo-test product, and the engine carries real data-loss risk. Counter: it's flagged OFF and reviewed, so landing the engine + design now (with live-verify owed) is pure upside — the capability exists the moment it's needed, without a rushed build under pressure.
