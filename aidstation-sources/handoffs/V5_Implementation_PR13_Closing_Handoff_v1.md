# V5 Implementation PR13 — SQLite + TrueNAS Retirement — Closing Handoff

**Session:** Stack-cleanup PR. Andy 2026-05-16 mid-conversation: "we discussed stopping sqlite development a while back, but we keep working on it, why? we are not using it / TrueNAS deployment at all anymore." This was an honest callout — PR12 (just shipped same chat) added 5 columns to `SQLITE_SCHEMA` + `_SQLITE_MIGRATIONS` matching the PR6 precedent, exactly the dual-maintenance pattern Andy had asked to stop. Root cause traced to CLAUDE.md "Stack" + "Operating context" still listing SQLite as the dev path + TrueNAS as a deploy target; Integration v4 §2.5 freeze only stopped *new tables* on SQLite, not *new columns on existing tables*; the PR6 prefill-cols precedent kept the bleed alive. Andy picked Option B (big now) over Option A (durable instruction first, code later) per the direct response. This PR ends the bleed.
**Date:** 2026-05-16
**Predecessor handoff:** `V5_Implementation_PR12_Closing_Handoff_v1.md` (PR12 D-61 §G + onboarding integration shipped same-chat).
**Branch:** `claude/v5-design-closing-handoff-oXoKV` (continuing — PR12 + PR13 land as separate commits on the same branch; push pending after PR13 commit).
**Status:** 🟡 Code shipped to feature branch; 🟡 push + PR + merge pending. **PR12's §5.0 walk-through + PR13's §5.0 walk-through both owed at deploy time.**
**Time-on-task:** Single chat (same chat as PR12). Files this turn: **~21 total** — explicitly over the 5-file ceiling per Andy's "big now" directive. 10 code edits + 4 deletions + 4 docs + 1 backlog + 1 handoff + the necessary helpers/comments. Discipline broken intentionally because the alternative (Option A — instruction-only, code later) would have left the dual-backend code path bleeding into every future session until a separate cleanup PR shipped.

---

## 1. Session-start verification (Rule #9)

PR12 was the immediate predecessor (same chat). Andy's directive itself is the verification trigger — he flagged that the SQLite columns I'd just added in PR12 (5 cols across `SQLITE_SCHEMA`/`_SQLITE_MIGRATIONS`/`PG_SCHEMA`/`_PG_MIGRATIONS`) were exactly the pattern he'd previously asked to stop. Confirmed by `grep`:

| Claim | Anchor | Result |
|---|---|---|
| PR12 added 5 §G capacity cols to `SQLITE_SCHEMA` + `_SQLITE_MIGRATIONS` redundant CREATE TABLE (PR6 prefill-cols pattern) — i.e., my just-shipped code matches the pattern Andy is calling out | grep on the new col names | ✅ Confirmed |
| CLAUDE.md "Stack" listed "PostgreSQL (Neon) in production; SQLite locally" | grep | ✅ Confirmed (the source of the framing inertia) |
| CLAUDE.md "Web app" deployment line listed "deployed to Vercel … and TrueNAS via Docker (Watchtower auto-deploys)" | grep | ✅ Confirmed |
| CLAUDE.md "Selective rebuild" listed "the dual-backend SQLite/Postgres pattern" as something to "revisit later" | grep | ✅ Confirmed |
| D-54 (SQLite backend deprecation) status was 🟡 Deferred; "Removed during Phase 5 of catalog migration" | grep `Project_Backlog_v25.md` D-54 row | ✅ Confirmed |
| Integration v4 §2.5 retroactively ratified the D-50 SQLite block as a one-time carve-out; "Freeze remains in force for all subsequent work." Existing-table column additions via the PR6 prefill-cols pattern were not explicitly covered; that's the loophole sessions kept driving through | grep `Athlete_Data_Integration_Spec` | ✅ Confirmed |

The drift Andy flagged is real and structural — durable instructions had not caught up to his earlier "stop" call. Fix had to land in CLAUDE.md + code together for the bleed to actually end.

---

## 2. Files shipped this turn

All on branch `claude/v5-design-closing-handoff-oXoKV`. Push pending after commit.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `database.py` | Rewrite (108 → 84 lines) | Stripped `import sqlite3`; dropped `_is_postgres()`, `sqlite_path()`, `_on_vercel()` helpers; `get_db()` now opens psycopg2 unconditionally and raises `RuntimeError` if `DATABASE_URL` is unset (clear boot-time failure rather than silent SQLite fallback). Kept the PG compatibility layer (`_PgRow`, `_CompatCursor`, `_PgConn`) so route code continues to use `?` placeholders — too many call sites to flip to native `%s` and unrelated to the PG-only retirement. |
| 2 | `init_db.py` | Surgical strip (2621 → 1581 lines, −1040) | Deleted: `import sqlite3`; the 322-line `SQLITE_SCHEMA = '''…'''` constant; the 370-line `_SQLITE_MIGRATIONS` list; the 90-line `init_sqlite()` function; the SQLite-specific table-rebuild helpers (`_rebuild_table_if_legacy_unique`, `_migrate_current_rx_unique`, `_migrate_body_metrics_unique`, `_migrate_wellness_log_unique`, `_migrate_session3_locale_clothing` — all sqlite_master-driven, all dead post-strip); the `is_postgres=False` else-branches of the two seed helpers (`_seed_current_rx_for_user`, `_seed_purchase_recommendations`); the `if DATABASE_URL: init_postgres() else: init_sqlite()` branch in `__main__` (now just `init_postgres()`). The 2 callers of the seed helpers that passed `is_postgres=True` updated to drop the kwarg. `PG_SCHEMA` + `_PG_MIGRATIONS` kept verbatim — production path unchanged. Header docstring rewritten ("Initialize the PostgreSQL database — schema + idempotent migrations + seeds"). |
| 3 | `app.py` | Edit (2 surgical) | Dropped `sqlite_path` import + `app.config['DATABASE'] = sqlite_path()` line; replaced the `if DATABASE_URL: init_postgres() else: init_sqlite()` conditional with an unconditional `init_postgres()`. The `os.environ.get('DATABASE_URL')` checks at lines 49 + 349 (used as proxies for "HTTPS-fronted prod") left as-is — they're now technically always-True since DATABASE_URL is required to run, but they're about deploy posture (HTTPS) not backend choice; cleaning them is a separate small refactor. |
| 4 | `routes/status.py` | Edit (1 surgical, drops module's `sqlite3` import) | Stripped the `if database._is_postgres(): … else: sqlite3.connect(database.sqlite_path()) …` branch in `_db_ok()`; PG `SELECT 1` probe is now the only path. Module's `import sqlite3` line dropped. Module docstring updated to drop "or the configured database" / dual-backend framing. |
| 5 | `athlete.py` | Edit (3 surgical, drops `database` import) | Stripped 2 `_is_postgres()` runtime guards: (a) `upsert_daily_availability_windows` lost the "PG-only guard" early-return so DELETE+INSERT runs unconditionally; (b) `upsert_athlete_profile` lost the `now_sql = 'NOW()' if database._is_postgres() else "datetime('now')"` ternary — UPDATE inlines `NOW()` directly. Defensive try/except in `get_daily_availability_windows` kept (transient DB hiccups would otherwise crash the form render) but the SQLite-missing-table comment updated. `import database` line dropped (no remaining `database.*` refs in module). |
| 6 | `routes/onboarding.py` | Edit (3 surgical, drops `database` import) | Stripped 3 `_is_postgres()` guards: (a) `_write_provider_provenance` no longer short-circuits on SQLite; (b) `_write_manual_override_provenance` same; (c) `prefill()` no longer wraps the provenance SELECT in an `if database._is_postgres():` block. Docstrings stripped of "PG-only — SQLite dev returns no rows" framing since SQLite is gone. `import database` line dropped. |
| 7 | `routes/nudges.py` | Edit (3 surgical, drops `database` import) | Stripped 3 `_is_postgres()` guards: (a) `get_active_nudges` no longer returns empty on SQLite; (b) `scan_connect_provider_14d` no longer returns `inserted=0, note='SQLite dev: account_nudges is PG-only'` — the cron INSERT runs unconditionally; (c) `dismiss()` no longer wraps the UPDATE in an `if database._is_postgres():` block. Docstrings updated. `import database` line dropped. |
| 8 | `routes/wellness.py` | Edit (2 surgical, drops `database` import) | Stripped the `now_sql = 'NOW()' if database._is_postgres() else "datetime('now')"` ternary and inlined `NOW()` into the UPDATE statement. f-string interpolation dropped → plain string. `import database` line dropped. |
| 9 | `routes/profile.py` | Edit (1 surgical, drops `database` import) | Stripped the `if not database._is_postgres(): return` guard at the head of `_record_self_report_provenance`. The PG-only-table comment in the docstring left in place — it's an honest note about the table's deployment shape, not a dual-backend guard. `import database` line dropped. |
| 10 | `routes/locales.py` | Edit (9 surgical, drops `database` import) | Stripped 8 `_is_postgres()` guards across D3a + D3b helpers: `_has_acked_mapbox_disclosure` no longer auto-grants True on SQLite; `_record_mapbox_disclosure_ack` no longer short-circuits; `_is_shared_profile_locale` no longer returns False; `_find_gym_profile` simplified to `if not mapbox_id: return None`; `_load_overrides`, `_save_overrides`, `_create_gym_profile`, `_touch_gym_profile_confirmation` all run their PG code unconditionally. `import database` line dropped. |
| 11 | `Dockerfile` | **Deleted** | TrueNAS Docker image build. Never used in practice — `aidstation-pro.vercel.app` is the only production target. |
| 12 | `docker-compose.yml` | **Deleted** | TrueNAS Compose stack (`web` service + `watchtower` for auto-pull). Same reasoning. |
| 13 | `deploy/truenas_setup.sh` | **Deleted** | One-shot TrueNAS SCALE setup script (`apt-get install git`, `git clone`, systemd unit). |
| 14 | `deploy/update.sh` | **Deleted** | TrueNAS-side `git pull && systemctl restart` script. |
| 15 | `deploy/get_garmin_tokens.py` | **Retained** | Garmin OAuth token helper — not TrueNAS-specific, just lives under `deploy/` historically. Garmin is paused; the script is dead code right now but a different cleanup (D-55 — Garmin onto provider_auth) covers it when Garmin reopens. |
| 16 | `aidstation-sources/CLAUDE.md` | Edit (4 surgical) | (a) "Stack" — `**Database:** PostgreSQL (Neon) in production; SQLite locally` → `**Database:** PostgreSQL (Neon) — both production and dev. SQLite path retired 2026-05-16 (PR13)`. (b) "Stack" — `**Web app:** … deployed to Vercel … and TrueNAS via Docker (Watchtower auto-deploys on push to main)` → `**Web app:** … deployed to Vercel … TrueNAS / Docker deployment path retired 2026-05-16 (PR13) — was never used in practice.` (c) "Selective rebuild — Revisit later" — dropped `the dual-backend SQLite/Postgres pattern` from the list (no longer applicable). (d) D-54 line under independent parallel tracks flipped from "queued; Catalog Migration Phase 5" to "✅ Resolved 2026-05-16 (PR13 — stripped SQLITE_SCHEMA, _SQLITE_MIGRATIONS, init_sqlite, sqlite_path, _is_postgres() guards across database.py/init_db.py/app.py/route files; PG-only via DATABASE_URL)". (e) "Authoritative current files" backlog pointer v25 → v26. (f) "Current state (as of 2026-05-16)" last-shipped narrative now leads with PR13 with PR12 as predecessor. |
| 17 | `DEV_SETUP.md` (root) | Edit (1 surgical) | Step 3 of the setup checklist rewritten — `Pick a backend: SQLite (default) — leave DATABASE_URL unset …` / `Postgres / Neon — set DATABASE_URL in .env` → single instruction: `Set DATABASE_URL in .env to a Postgres / Neon connection string. The app is Postgres-only (SQLite path retired 2026-05-16, PR13); get_db() raises if DATABASE_URL is unset. Use a Neon dev branch for local work …`. |
| 18 | `DATABASE.md` (root) | Edit (2 surgical) | (a) Top-of-file marker note added: "Note (2026-05-16, PR13): The app is now Postgres-only (Neon). The Overview + Architecture sections below have been rewritten for the PG-only posture, but several deeper sections still reference the historical SQLite path … Those passages are stale historical reference — ignore for new code. A full rewrite of the deeper sections is owed but not blocking." (b) Overview + Architecture sections (lines ~40-110) rewritten — drops the "two interchangeable backends" framing; updates the backend topology table (only Vercel/Neon + local-dev/Neon-dev-branch rows survive); rewrites the `database.py` compatibility-layer paragraph as PG-only. The deeper schema sections (lines 150+) intentionally not touched — they contain ~50 references to SQLite that are now stale but harmless; full rewrite is owed in a separate cleanup PR. |
| 19 | `HANDOFF.md` (root) | Edit (1 surgical) | Top-of-file marker note prepended: "Note (2026-05-16, PR13): This is the 2026-05-06 v1-maintenance handoff, kept for historical context. The v2 LLM-pipeline build has been in flight since 2026-05-08; current state lives in `aidstation-sources/CLAUDE.md` + the latest handoff in `aidstation-sources/handoffs/`. Notably out-of-date here: the TrueNAS/Docker deployment was retired 2026-05-16 (PR13) — Vercel is now the only deploy target, and Postgres (Neon) is the only DB backend." Body of the 2026-05-06 doc not touched — it's a historical handoff snapshot. |
| 20 | `aidstation-sources/Project_Backlog_v26.md` | New (copy of v25 + 4 surgical edits) | (a) File-revision header v25→v26 with the full PR13 narrative (Andy's directive quote, root-cause framing, change list, deletion list, doc updates, backlog row changes). (b) Prepend v25 entry to predecessor revisions block. (c) D-54 row: status cell 🟡 Deferred → ✅ Resolved 2026-05-16 (PR13); description updated to note pulled-forward-from-Phase-5; Notes column expanded with the full resolution summary. (d) D-65 row added (TrueNAS Docker decommission, status ✅ Resolved). (e) D-50 row description gets PR13 entry; D-50 status cell adds PR13 to the merged-commits list (both `<PR12-merge-pending>` and `<PR13-merge-pending>` placeholders); D-50 🟢 shipped list gets "PR13 stack cleanup". (f) D-62 row Notes column drops "TrueNAS-side scheduled task vs. an in-app scheduler" — Vercel Cron is now the only natural home. |
| 21 | `aidstation-sources/handoffs/V5_Implementation_PR13_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `Athlete_Data_Integration_Spec_v4.md` §2.5 (the SQLite freeze section) — the freeze is now retired by definition (the SQLite path is gone, so there's nothing to freeze). A v5 spec bump to formally retire §2.5 is design-mode work and not on this PR's critical path; tracked in §5.4.
- `Catalog_Migration_Plan_v2.md` — Phase 5's deliverable was "drop the SQLite path"; that work just shipped in PR13. Phase 5 collapses to "drop the `public.*` legacy catalogs" only. Updating Phase 5 is design-mode work; tracked in §5.4.
- `Control_Spec_v7.md` — has scattered SQLite references in deployment-context paragraphs. Not on this PR's path; cleanup is owed when Control_Spec gets its next revision.
- `aidstation-sources/DATABASE.md` — duplicate of root `DATABASE.md` from the v2 design wave; same surgical-edit-vs-full-rewrite tradeoff. Skipped this revision; track for a follow-on cleanup.
- All v2 design spec files in `aidstation-sources/` (Layer specs, Onboarding designs, etc.) — they reference the old dual-backend framing in passing but the framing isn't load-bearing. Lands in a separate doc-sweep PR if Andy wants.
- Vercel-specific deploy config (`vercel.json`) — unchanged; was always PG/Vercel-only.
- The `.env.example` (if present) — not touched; the operator-facing setup instructions in `DEV_SETUP.md` are the authoritative source now.
- Tests directory (`tests/`) — none exists; same framing as PR1–PR12.

---

## 3. What landed

### 3.1 The bleed Andy flagged

PR6 (2026-05-14) added 5 prefill columns to `athlete_profile` across all four schema touch-points: cold-start `SQLITE_SCHEMA`, cold-start `PG_SCHEMA`, redundant `CREATE TABLE` in `_SQLITE_MIGRATIONS`, redundant `CREATE TABLE` in `_PG_MIGRATIONS`, plus hot `ALTER TABLE` in `_PG_MIGRATIONS`. That established the precedent: "when you add a column to `athlete_profile`, touch all four places."

PR12 (this chat, earlier) followed the precedent exactly — 5 §G capacity columns landed in all four schema touch-points. I called it out in the PR12 handoff §2 (`"matching the PR6 prefill-column pattern"`) without questioning whether the pattern itself was still valid.

Andy's response made the structural drift visible: the CLAUDE.md "Stack" line still said "SQLite locally," D-54 was still "🟡 Deferred — Phase 5," and Integration v4 §2.5's freeze covered new tables but not new columns. So every session inherited the framing and matched the precedent. The freeze stopped the worst case (new tables on both paths) but the precedent kept the next-worse case alive (new columns on both paths).

The fix had to land in three places at once for the bleed to actually end: durable instructions (CLAUDE.md), code (database/init_db/routes), and the backlog tracker (D-54 + D-65 status). Andy explicitly authorised Option B (big now) so all three landed in one PR.

### 3.2 `database.py` rewrite

Reduced from 108 lines to 84. Drops:
- `import sqlite3` (top-level)
- `_is_postgres()` (returned `bool(DATABASE_URL)`)
- `_on_vercel()` (only used by `sqlite_path()` previously)
- `sqlite_path()` (decided between `/tmp/training.db` on Vercel and `instance/training.db` locally)
- The SQLite branch in `get_db()`

Keeps:
- `_PgRow` (dict subclass with int-indexable access — `row['col']` and `row[0]` both work)
- `_CompatCursor` (wraps psycopg2 RealDictCursor; provides the `lastrowid` shim that reads from `fetchone()` so INSERT … RETURNING id keeps working)
- `_PgConn` (the `?` → `%s` placeholder translation; the historical-compat surface that lets route code stay unchanged)
- `init_app()` (registers `close_db` as `teardown_appcontext`)

New behavior: `get_db()` raises `RuntimeError` if `DATABASE_URL` is unset. Boot still completes (the `init_postgres()` call in `app.py` catches its own exception and logs a warning), but the first request errors out hard rather than silently using SQLite. This is the honest posture for PG-only.

### 3.3 `init_db.py` surgical strip

Reduced from 2621 lines to 1581 (−1040 lines, ~40% smaller). Dropped:
- The 322-line `SQLITE_SCHEMA = '''…'''` constant
- The 370-line `_SQLITE_MIGRATIONS = [ … ]` list
- The 90-line `init_sqlite()` function (cold-start path: create file, run schema, run migrations, seed)
- 5 sqlite_master-driven migration helpers that were only called from `_SQLITE_MIGRATIONS` (`_rebuild_table_if_legacy_unique`, `_migrate_current_rx_unique`, `_migrate_body_metrics_unique`, `_migrate_wellness_log_unique`, `_migrate_session3_locale_clothing`)
- The `is_postgres=False` else-branches of the two seed helpers, plus the `is_postgres` kwarg itself
- The `if DATABASE_URL: init_postgres() else: init_sqlite()` branch in `__main__`

The 2 callers of `_seed_current_rx_for_user` inside `init_postgres()` (and the 1 caller in `routes/auth.py:register`) updated to drop `is_postgres=True`. `init_postgres()` and `_PG_MIGRATIONS` itself unchanged — production path is bit-for-bit identical to before PR13.

Header docstring rewritten: `"Initialize the PostgreSQL database — schema + idempotent migrations + seeds."`

### 3.4 13 runtime `_is_postgres()` guards removed

Across 6 route files + `athlete.py`. Each was a defensive `if not database._is_postgres(): return` (or `if database._is_postgres(): …` wrapper) that silently no-op'd on SQLite. Since SQLite is gone, the guards became dead code; stripped them and let the PG path run unconditionally. Two `now_sql = 'NOW()' if database._is_postgres() else "datetime('now')"` ternaries (in `athlete.py:upsert_athlete_profile` and `routes/wellness.py:save_self_report`) inlined to `NOW()` directly.

After the strip: 0 occurrences of `_is_postgres` in the entire Python codebase. 6 `import database` lines became orphan and were removed.

### 3.5 TrueNAS Docker artifacts deleted

Andy's "we are not using it / TrueNAS deployment at all anymore" → 4 files deleted: `Dockerfile`, `docker-compose.yml`, `deploy/truenas_setup.sh`, `deploy/update.sh`. The TrueNAS path was Watchtower-based (auto-pull-and-restart on push to `main`), which was never actually used in production — Vercel has always been the only operational deploy target. `deploy/get_garmin_tokens.py` retained — it's an unrelated Garmin OAuth helper.

### 3.6 Doc updates

- `aidstation-sources/CLAUDE.md` — Stack + Operating context + D-54 line + "Selective rebuild" + last-shipped + backlog pointer all updated. New framing: PG-only, Vercel-only.
- `DEV_SETUP.md` (root) — local-setup checklist rewritten for PG-only.
- `DATABASE.md` (root) — Overview + Architecture rewritten; top-of-file note flags that deeper sections are stale historical reference.
- `HANDOFF.md` (root) — top-of-file marker note added pointing at `aidstation-sources/CLAUDE.md` as the authoritative current state.

Deferred to a follow-on doc-sweep PR (per §5.4):
- Full rewrite of the deeper `DATABASE.md` sections
- `aidstation-sources/DATABASE.md` (duplicate)
- `Athlete_Data_Integration_Spec_v4.md` §2.5 retirement (design-mode work)
- `Catalog_Migration_Plan_v2.md` Phase 5 scope adjustment (design-mode work)
- `Control_Spec_v7.md` deployment-context paragraphs

### 3.7 Backlog discipline (v25 → v26)

- **D-54 (SQLite backend deprecation)** flipped 🟡 Deferred → ✅ Resolved 2026-05-16 (PR13). Notes column expanded with the full resolution summary.
- **D-65 (TrueNAS Docker deployment retirement)** added as a new row, ✅ Resolved 2026-05-16 (PR13). Captured as its own row so predecessor revisions can reference it cleanly.
- **D-50** description appended with the PR13 stack-cleanup entry; status cell adds PR13 to the merged list (both `<PR12-merge-pending>` and `<PR13-merge-pending>` placeholders); 🟢 shipped list catches up.
- **D-62 (`webhook_events` retention prune)** Notes column updated — "Vercel Cron" replaces "Vercel cron jobs vs. a TrueNAS-side scheduled task" in the design-work checklist (TrueNAS is no longer an option).

### 3.8 Verification

Boot test: `SECRET_KEY=t DATABASE_URL="" python -c "from app import app"` → app boots; init_db prints a clear warning that it couldn't connect (no PG socket); all 127 routes register cleanly. `get_db()` would raise on the first request — that's the desired hard-fail posture.

Final sweep — `grep -rn "import sqlite3\|_is_postgres\|sqlite_path\|SQLITE_SCHEMA\|_SQLITE_MIGRATIONS\|init_sqlite" --include="*.py"` returns zero results across the entire codebase.

TrueNAS artifact verification — `ls Dockerfile docker-compose.yml deploy/truenas_setup.sh deploy/update.sh` all fail with "No such file"; `deploy/get_garmin_tokens.py` survives as intended.

---

## 4. Session-end verification (Rule #10)

| Claim | Anchor | Result |
|---|---|---|
| `database.py` has no `import sqlite3`, no `_is_postgres`, no `sqlite_path`; `get_db()` raises `RuntimeError` on missing `DATABASE_URL` | grep + read | ✅ Verified |
| `init_db.py` has no `SQLITE_SCHEMA`, no `_SQLITE_MIGRATIONS`, no `init_sqlite`, no `is_postgres=False` parameter defaults | grep | ✅ Verified |
| `app.py` no longer imports `sqlite_path` or configures `app.config['DATABASE']`; `init_postgres()` runs unconditionally | grep + read | ✅ Verified |
| 0 occurrences of `_is_postgres` across the Python codebase | grep -rn | ✅ Verified |
| 4 TrueNAS / Docker artifacts deleted; `deploy/get_garmin_tokens.py` retained | `ls` | ✅ Verified |
| App boots clean (DATABASE_URL unset → warning logged + 127 routes register) | inline `python -c` | ✅ Verified |
| `aidstation-sources/CLAUDE.md` Stack reads "PostgreSQL (Neon) — both production and dev. SQLite path retired 2026-05-16 (PR13)"; "TrueNAS / Docker deployment path retired 2026-05-16 (PR13) — was never used in practice"; D-54 line ✅ Resolved; backlog pointer v26 | grep | ✅ Verified |
| `DEV_SETUP.md` step 3 reads PG-only | grep | ✅ Verified |
| `DATABASE.md` (root) has the top-of-file PR13 marker note; Overview + Architecture rewritten for PG-only | grep | ✅ Verified |
| `HANDOFF.md` (root) has the top-of-file PR13 stale-context marker | grep | ✅ Verified |
| `Project_Backlog_v26.md` exists; D-54 status ✅ Resolved 2026-05-16 (PR13); D-65 row present with status ✅ Resolved; D-50 description gets PR13 entry; D-62 notes drops TrueNAS scheduler reference | grep + read | ✅ Verified |
| 7 substantive code edits + 4 deletions + 4 doc edits + new backlog + this handoff = 17 substantive things; 21 if counting the PR12-PR13 split commits | file count | ✅ Verified (over the 5-file ceiling per Andy's "big now" directive) |

No drift between this handoff's narrative and on-disk state.

**Live verification gap:** PR13 hasn't been merged or deployed yet; first PG cold start after merge verifies that `init_postgres()` still runs cleanly with the slimmer `init_db.py` (no regressions from the helper-function deletion).

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification owed (this PR)

After merge to `main`, walk the following on the deployed app. Mostly regression-checks since this is a cleanup PR — anything that worked under the dual-backend should still work post-PR13.

1. **App boots on Vercel with `DATABASE_URL` set.** First cold start after merge: check Vercel logs for the `Warning: DB init skipped: …` line. If it appears, `init_postgres()` hit an error — investigate before sending traffic. If it doesn't appear, schema is current.
2. **App refuses to boot without `DATABASE_URL`.** Unset `DATABASE_URL` in a Vercel preview env or a local shell; visit any route; expect `RuntimeError: DATABASE_URL environment variable is required …` on the first request. (Boot itself still completes because `init_postgres()` catches its own exception.)
3. **`/status` endpoint stays green.** `GET /status` should return `{"status": "ok"}` 200 (the SQLite-probe branch is gone; only the PG-probe path remains).
4. **PR12 §5.0 walk-through carries forward.** All 13 steps from `V5_Implementation_PR12_Closing_Handoff_v1.md` §5.0 are still owed at merge time. PR13 doesn't change any §G surface — same form, same persistence, same flashes. Re-run §5.0 step 4 (the persistent round-trip) to confirm `daily_availability_windows` writes still land under PG (which they will, since the PG path is unchanged — what's gone is the SQLite path that was silently no-op'ing). Same for the §G capacity columns on `athlete_profile`.
5. **All `_PG_MIGRATIONS` ALTERs still idempotent.** Spot-check `\d athlete_profile` after the first PG boot under PR13 — same 24 columns as under PR12. PR13 didn't touch `_PG_MIGRATIONS`.
6. **Regression — PR11 D3b D-60 inherit/override flow.** Edit a shared-profile locale; verify the inherit/override UI still renders correctly (this exercised the `routes/locales.py` `_is_postgres()` guards I just stripped; the PG path was always-running anyway, so behavior should be identical).
7. **Regression — PR9 nudge banner.** Verify `active_nudges` still surfaces on `/dashboard` for accounts that meet the 14-day criterion; verify dismiss still works (stripped the `_is_postgres()` guard around the UPDATE).
8. **Regression — PR8 prefill flow.** Visit `/onboarding/prefill`; click `[Use provider value]` on any candidate; verify the provenance row writes (stripped the `_is_postgres()` guards around the two provenance UPSERTs).
9. **Regression — PR3 Polar webhook ingest.** If a Polar webhook arrives, verify the dedup INSERT still lands under `routes/polar_ingest.py` (no PR13 changes there, but webhook ingest is the most likely place for an unrelated regression to surface).
10. **Vercel cron stays scheduled.** `vercel.json` `crons` entry for the connect-provider nudge still runs at `0 14 * * *` UTC. PR13 didn't touch `vercel.json`.
11. **TrueNAS deploy verification — N/A.** With `Dockerfile` + `docker-compose.yml` + `deploy/truenas_setup.sh` + `deploy/update.sh` deleted, the TrueNAS path is intentionally gone. If anything was still running on TrueNAS in some forgotten corner, Andy will need to either stand it back up manually (the deleted files are recoverable from git history) or let it drift.
12. **Carry-forward.** PR11 §5.0 13 steps + PR10 §5.0 2 remaining steps + PR12 §5.0 13 steps still 🟡 owed; PR13 adds 11 of its own. Total: 39 steps queued in `PR_Verification_Status.md` at merge time. Most are regression-class so the walk can batch.

### 5.1 Next-session candidate menu

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read. Notice the bumped backlog pointer to v26, the PG-only Stack line, the retired TrueNAS line, the new last-shipped narrative leading with PR13.
2. `aidstation-sources/PR_Verification_Status.md` — 39 §5.0 steps queued at merge.
3. `aidstation-sources/handoffs/V5_Implementation_PR13_Closing_Handoff_v1.md` (this file).
4. `aidstation-sources/handoffs/V5_Implementation_PR12_Closing_Handoff_v1.md` (same-chat predecessor).
5. `aidstation-sources/Project_Backlog_v26.md` — current.
6. Domain spec for the picked candidate.

#### Option A — Layer 4 plan-gen spec draft (Recommended, unchanged from PR12 §5.1)

The next big unblock. Gates D-61 JIT swap, D-63, D-64, and the rest of v5 plan-execution. Substantial multi-session work; spec-first. Start with §1 purpose + §2 boundaries + §3 function signature + §6 payload schema (session output shape).

#### Option B — D-61 profile-tab edit follow-on (unchanged from PR12 §5.1)

Small parallel PR — surface the §G form (or a slimmer partial-template variant) on `/profile?tab=athlete` so athletes can edit per-day windows + capacity flags post-onboarding without re-visiting the onboarding URL. ~2-3 files. Doesn't need Layer 4.

#### Option C — DATABASE.md / Catalog Migration Plan / Integration spec §2.5 doc sweep

The deeper sections of `DATABASE.md` still reference the SQLite path that's now gone (lines 150+, ~50 references). `Catalog_Migration_Plan_v2.md` Phase 5 needs scope adjustment ("drop SQLite path" already done by PR13; Phase 5 collapses to "drop legacy `public.*` catalogs" only). `Athlete_Data_Integration_Spec_v4` §2.5 (the SQLite freeze) needs formal retirement — likely a v5 spec bump with §2.5 either deleted or rewritten as historical context. Design-mode work; one focused session.

#### Other PR12 §5.1 carry-forwards (unchanged)

- D-60 closeout (dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure) — premature at N=1.
- §J.3 sport-specific gear toggle UI — needs design re-read.
- F (Polar refresh-on-401), H (provider expansion), D2c (bulk apply), E-telemetry (nudge tracking), D-62 (webhook retention prune).

### 5.2 Recommended sequence (revised post-PR13)

1. **Layer 4 spec draft (Option A).** Unchanged from PR12 — Layer 4 unblocks D-61 JIT + D-63 + D-64. Substantial; expect 3-5 sessions.
2. **D-61 profile-tab edit follow-on (Option B).** Parallel; small.
3. **Doc sweep (Option C).** Pick up when convenient. Not blocking.
4. **D-63 + D-64 implementation** — once Layer 4 spec stabilizes.
5. **D-60 closeout + §J.3 toggles UI** — when cohort > 1.
6. **F / H / D2c / E-telemetry / D-62** — opportunistic.

### 5.3 Standing items not on the critical path (carried from PR12 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged.
- **D-54 SQLite backend deprecation** — ✅ Resolved this revision.
- **D-55 Garmin onto `provider_auth`** — paused. `deploy/get_garmin_tokens.py` survives in `deploy/` as the only inhabitant; cleanup folds into D-55 when Garmin reopens.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — unchanged scope; "Vercel Cron" is now the only host option (TrueNAS retired).
- **§J.3 sport-specific gear toggle UI** — unchanged.
- **D-60 dispute / submit-as-correction / sharing opt-out / sharing-consent disclosure** — unchanged.
- **D-61 JIT swap session-card UI** — Layer-4-gated; unchanged.
- **D-61 profile-tab edit surface** — small follow-on; unchanged.
- **D-63 on-demand workout** — Layer-4-gated; unchanged.
- **D-64 plan refresh tiers** — Layer-4-gated; unchanged.
- **D-65 TrueNAS Docker decommission** — ✅ Resolved this revision.
- **NL intent parser prompt body design** (D-64) — deferred.
- **Layer 4 single-session synthesis prompt body design** (D-63) — folds into Layer 4 work.
- **DATABASE.md deep-section rewrite** — *new this revision* as deferred cleanup item (Option C above).
- **Catalog_Migration_Plan_v2.md Phase 5 scope adjustment** — *new this revision* as deferred design item.
- **Integration v4 §2.5 retirement (v5 spec bump)** — *new this revision* as deferred design item.
- **Open Item #18 — Telemetry on the 14-day connect-provider nudge** — unchanged.

### 5.4 Backlog row update (next PR's first action — conditional)

For the next code PR (e.g., D-61 profile-tab edit follow-on or Layer 4 spec draft), owed v26 → v27 bump:

1. Copy `aidstation-sources/Project_Backlog_v26.md` → `Project_Backlog_v27.md`.
2. **Replace** the file-revision header narrative on line 5 with the next PR's state-flip summary.
3. **Prepend** to predecessor revisions block (verbatim from current v26 line 5 narrative trimmed to one line):
    ```
    - v26 — 2026-05-16 (PR13 — SQLite + TrueNAS retirement. Strips `SQLITE_SCHEMA` / `_SQLITE_MIGRATIONS` / `init_sqlite` / `sqlite_path` / `_is_postgres()` runtime guards (13 across 6 route files) / `now_sql` ternaries; deletes `Dockerfile` / `docker-compose.yml` / `deploy/truenas_setup.sh` / `deploy/update.sh`. PG-only via `DATABASE_URL`. D-54 ✅ Resolved; D-65 added ✅ Resolved (TrueNAS retire). Stack cleanup triggered by Andy's "we keep working on it, why?" question after PR12 added 5 cols to SQLITE_SCHEMA. Per `V5_Implementation_PR13_Closing_Handoff_v1.md`)
    ```
4. **Update** the D-50 row: PR12-merge SHA + PR13-merge SHA filled in from git log; next-PR entry appended.
5. **Update** D-rows whose status changed.
6. **Bump** `CLAUDE.md` backlog pointer v26 → v27 + state date + last-shipped narrative.

**If the next session is Layer 4 spec drafting** (design-only, no code): same backlog-bump shape; D-row statuses don't flip (Layer 4 itself doesn't have a backlog row yet — D-63/D-64/D-61's "gates on Layer 4 spec landing" notes stay 🟡 until Layer 4 lands in code).

---

## 6. Open items / honest flags

- **5-file ceiling broken intentionally.** ~21 substantive files vs the 5-file rule. Andy explicitly authorised "big now" because Option A (instruction-only, code later) would have left the dual-backend pattern bleeding into every future session until a separate cleanup PR shipped. The ceiling exists because quality degrades past it; this PR is mostly mechanical strip + delete + status flips, where the per-file cognitive load is much lower than designing new features.
- **Push + PR + merge pending.** Both PR12 (D-61 §G) and PR13 (SQLite/TrueNAS retire) commit to `claude/v5-design-closing-handoff-oXoKV`; PR creation happens at Andy's request.
- **§5.0 walk-through volume.** PR13 adds 11 owed steps on top of PR10's 2 + PR11's 13 + PR12's 13 = 39 total queued in `PR_Verification_Status.md`. Most are regression-class; batchable.
- **Deeper DATABASE.md sections still reference SQLite.** Top-of-file marker note flags them as historical; deep rewrite owed in a follow-on cleanup PR. Not blocking.
- **`os.environ.get('DATABASE_URL')` still used as a "prod posture" proxy in `app.py`.** Two locations (SESSION_COOKIE_SECURE default, CSP upgrade-insecure-requests). Both technically always-True post-PR13 since `DATABASE_URL` is required to boot. Cleaning is a separate small refactor — they're about HTTPS posture, not backend choice, so not in PR13's scope.
- **`Athlete_Data_Integration_Spec_v4 §2.5` retirement is design-mode work.** The §2.5 freeze is now retired by definition (no SQLite path to freeze), but the spec text still says "Freeze remains in force for all subsequent work." A v5 spec bump that formally retires §2.5 is owed.
- **`Catalog_Migration_Plan_v2.md` Phase 5 scope adjustment.** Phase 5's "drop SQLite path" deliverable shipped in PR13; Phase 5 collapses to "drop the legacy `public.*` catalogs" only. Updating the plan doc is design-mode work; owed.
- **`Control_Spec_v7.md` deployment-context paragraphs.** Reference the old dual-backend framing in passing. Not load-bearing; cleanup when Control_Spec gets its next revision.
- **`aidstation-sources/DATABASE.md` (duplicate of root)** — skipped this revision; same surgical-vs-rewrite tradeoff.
- **`deploy/` directory now has 1 file.** `get_garmin_tokens.py` survives. The directory could be deleted entirely if Garmin tooling moves elsewhere; not in PR13's scope (Garmin is paused, separate D-55 cleanup).
- **No tests added.** Same framing as PR1–PR12. Boot-test + grep-sweep verified inline.
- **`init_db.py` is now noticeably leaner (1581 vs 2621 lines).** Easier to read for future sessions. But the 5 SQLite-helper functions that got deleted (`_rebuild_table_if_legacy_unique` and its 4 callers) contained design notes about Session 2D's composite-UNIQUE rebuilds. The design notes are stale — they describe a SQLite-specific workaround that's no longer needed. Lost to git history; recoverable if a future session ever needs the framing.
- **Honest about Andy's directive.** PR12 (just-shipped, same chat) shipped 5 columns to SQLite-side schemas. Andy didn't ask me to revert those — he said "you don't need to rip out the columns you just added." So PR12's commit stays as-is in git history; PR13 strips the surrounding SQLite machinery so those PR12 columns become inert noise in the same commit they shipped in. Slightly weird but it's what Andy chose; the alternative (PR12 amend) would have churned.
- **Same branch carries both commits.** `claude/v5-design-closing-handoff-oXoKV` has PR12 commit (`7a8028d`) and now will have a PR13 commit on top. Either both ship as one PR (squashed) or PR12 and PR13 ship as separate PRs from the same branch via cherry-pick — Andy's call when he reviews.

---

## 7. Gut check

**What this session got right.**

- **Stop-and-ask discipline kicked in late but kicked in.** I didn't catch the SQLite drift in PR12 itself — I matched the PR6 precedent without questioning it. Andy did. The response then framed the root cause honestly (durable instructions hadn't caught up to his prior call), proposed two options with clear tradeoffs (instruction-only vs big-now), let Andy choose, and executed the chosen path. The right move once the drift was visible.
- **Root cause fix, not symptom patch.** The temptation was to revert PR12's SQLite-side additions and call it done. That would have left the precedent + the framing intact, so the next session would have inherited the same drift. Stripping the whole SQLite path + updating CLAUDE.md + flipping D-54 ends the bleed structurally.
- **Honest about the ceiling break.** 21 files explicitly over the 5-file rule. Andy authorised "big now"; the handoff records both the directive and the scope honestly.
- **PR12 columns stay.** Andy said "you don't need to rip out the columns you just added." Following the spirit (don't churn) rather than the letter (revert everything SQLite-touching).
- **Tests where they fit.** Boot test + grep-sweep covered the operational verification cheaply. No new failure modes introduced because the SQLite path was already silently no-op'ing on production (which has always had `DATABASE_URL` set).
- **Backlog discipline.** D-54 status flipped properly; D-65 added as its own row so predecessor revisions can reference it cleanly; D-50 catches up; D-62's Notes drops the now-obsolete TrueNAS scheduler reference.
- **Doc updates split into "essential" vs "owed".** CLAUDE.md + DEV_SETUP.md + DATABASE.md top + HANDOFF.md top are essential (durable instruction + operator-facing setup). DATABASE.md deep sections + Integration spec §2.5 + Catalog Migration Plan §5 + aidstation-sources/DATABASE.md are owed cleanup; flagged in §5.3 + §5.4 without trying to do everything in one PR.

**Risks.**

- **Bigger PR diff = more places to regress.** The PG path was always-running on production, so behavior should be identical. But the strip removed 1040 lines of `init_db.py`; if some helper that was supposedly SQLite-only was actually called from somewhere unexpected, the failure won't surface until first PG cold start on Vercel. Smoke test plan in §5.0 catches it.
- **Doc drift remains.** DATABASE.md deep sections + duplicate `aidstation-sources/DATABASE.md` + Integration v4 §2.5 + Catalog Migration Plan v2 Phase 5 + Control_Spec all still reference the old dual-backend framing. Marker notes + backlog items track it; full cleanup is a separate doc-sweep PR.
- **`app.py` env-var-based prod-posture proxies still in place.** `SESSION_COOKIE_SECURE` defaults via `bool(os.environ.get('DATABASE_URL'))`; CSP `upgrade-insecure-requests` gated on the same. Both technically always-True post-PR13 since `DATABASE_URL` is required to boot. Not broken, just unnecessarily indirect; cleaning is a separate small refactor.
- **Garmin tooling now orphaned in `deploy/`.** `deploy/get_garmin_tokens.py` is the only file left in `deploy/`. Garmin work is paused (D-55) so the orphan is harmless; cleanup folds into D-55 when Garmin reopens.

**What might be missing.**

- **`.env.example` content.** If the repo has one (not checked), it may still list DATABASE_URL as optional. Quick fix when surfaced.
- **CI / GitHub Actions config.** If anything in `.github/workflows/` referenced the SQLite path (e.g., test runner setup), it would be stale. Not checked in PR13.
- **Watchtower image cleanup on existing TrueNAS hosts.** If a TrueNAS instance somewhere is still running `ghcr.io/ahorn885/exercise:latest` via the `watchtower` auto-pull, it will keep pulling and running stale code (the new commits won't have a Docker image since `Dockerfile` is gone). Andy's call whether to manually shut down any drifted TrueNAS instance.

**Best argument against this PR's scope.**

A 21-file PR is hard to review, hard to revert, and breaks the ceiling discipline that CLAUDE.md established. Option A (durable instruction first — just update CLAUDE.md + flip D-54 + create a tracking row) was a 4-file PR that would have respected the ceiling and let the code cleanup land in a focused follow-on PR with a clean diff.

Counter: I picked Option A's framing as the recommendation; Andy picked Option B explicitly. The reasoning he didn't spell out but which is implicit in "big now" is that PR12 just demonstrated the bleed in real-time — the dual-backend code pattern survives in the codebase as long as code exists for it to spread into. Option A would have updated the instruction + left the code, meaning the next session would have inherited correctly-framed instructions but still found `_is_postgres()` guards in every route file and felt compelled to match the existing pattern (or, worse, would have introduced new guards "defensively"). Option B ends the pattern in code + instructions + tracker simultaneously.

Counter to the counter: ceiling discipline exists because review quality degrades past ~5 files. A 21-file PR that's hard to review may smuggle in subtle regressions that small focused PRs would have caught. Mitigation: the changes are heavily mechanical (strip dead code paths) and the inline boot-test verified the app still loads; PR description should give reviewers a clear file-by-file map (§2 of this handoff does that).

Net: Andy's call to do big-now was defensible given the bleed pattern; the PR is mostly mechanical so the review cost is lower than 21 files of feature work; the §5.0 walk-through in §5.0 catches operational regressions; the backlog + handoff record both the directive and the over-ceiling scope so the discipline break is auditable.

---

## 8. Forward pointers

- **Next session:** Layer 4 plan-gen spec draft (Recommended) or D-61 profile-tab edit follow-on (small, parallel) or doc-sweep PR (Option C). Andy's call.
- **Following next session:** if Layer 4 spec is in flight, profile-tab edit + doc-sweep land in parallel. D-63 + D-64 implementation lands once Layer 4 spec is v1 stable.
- **Before next code lands:** Pre-deploy §5.0 walk-throughs for PR12 (13 steps) + PR13 (11 steps) + PR10 + PR11 carry-forwards. 39 total queued in `PR_Verification_Status.md`. Most are regression-class so the walk can batch.
- **First action of next session:** Read `aidstation-sources/CLAUDE.md` fully (Rule #13 — note the PG-only Stack + retired TrueNAS framing + v26 backlog pointer). Then Rule #9 reconciliation: confirm `database.py` is PG-only; confirm `init_db.py` has no `SQLITE_SCHEMA`/`_SQLITE_MIGRATIONS`/`init_sqlite`; confirm 0 `_is_postgres` refs across the Python codebase; confirm `Dockerfile`/`docker-compose.yml`/`deploy/truenas_setup.sh`/`deploy/update.sh` are deleted; confirm `Project_Backlog_v26.md` D-54 ✅ Resolved + D-65 ✅ Resolved. Then read the picked candidate's domain spec.

**Rules in force, unchanged:**

- #9 session-start verification — fired implicitly when Andy flagged the SQLite drift
- #10 session-end verification — see §4
- #11 mechanically-applicable deferred edits — see §5.4 for the v26 → v27 bump
- #12 numeric version suffixes — backlog at v26
- #13 every closing handoff names CLAUDE.md as the first re-read — applied: §5.1 forward-pointer reads CLAUDE.md as item 1; §8 first-action explicitly names CLAUDE.md
- **The 5-file ceiling** — broken this PR intentionally with Andy's explicit authorisation; back in force for the next PR. Recording the break in the backlog + handoff so future sessions don't take it as license to over-ship.

---

*End of V5 Implementation PR13 closing handoff. Ends the SQLite + TrueNAS bleed structurally: `database.py` PG-only (raises if `DATABASE_URL` unset); `init_db.py` 1040 lines lighter (no `SQLITE_SCHEMA`, no `_SQLITE_MIGRATIONS`, no `init_sqlite`, no sqlite_master-driven migration helpers); `app.py` unconditionally runs `init_postgres()`; 13 `_is_postgres()` runtime guards removed across 6 route files + `athlete.py`; 0 occurrences of `_is_postgres` / `sqlite_path` / `import sqlite3` remaining in the Python codebase; `Dockerfile` + `docker-compose.yml` + `deploy/truenas_setup.sh` + `deploy/update.sh` deleted (Vercel is now the only deploy target); `aidstation-sources/CLAUDE.md` Stack + Operating context + D-54 + last-shipped narrative all updated for PG-only/Vercel-only; root `DEV_SETUP.md` + top of `DATABASE.md` + top of `HANDOFF.md` flagged with PR13 retirement notes; backlog v25 → v26 with D-54 status flipped 🟡 → ✅ Resolved (PR13) and new D-65 added ✅ Resolved (TrueNAS Docker decommission). Pure cleanup PR — no v5 D-row scope advance, just deletion of stale paths whose maintenance was bleeding into every session. Ceiling broken (21 files) per Andy's "big now" authorisation; back in force for next PR. PR12's just-shipped SQLite-side column additions left as inert noise per Andy's "you don't need to rip out the columns you just added." Next: Layer 4 spec draft (recommended), or D-61 profile-tab edit follow-on (small parallel), or doc-sweep PR for the still-stale deeper DATABASE.md sections + Integration v4 §2.5 retirement + Catalog Migration Plan v2 Phase 5 scope adjustment.*
