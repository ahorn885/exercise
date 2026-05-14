# D-50 Phase 1 Schema — Handoff Review

**Reviewing:** `aidstation-sources/handoffs/D50_Phase1_Schema_Closing_Handoff_v1.md`
**Reviewed commit:** `909dc17` — *"D-50 Phase 1 schema: provider_auth + webhook_events + Polar/Wahoo/COROS tables"*
**Review date:** 2026-05-14
**Verifier branch:** `claude/review-aidstation-handoff-4aRtE`
**Method:** Rule #9 anchor checks against on-disk state; spec-compliance cross-read against `Athlete_Data_Integration_Spec_v3.md` §4–§6; runtime-path audit of `init_db.py` / `database.py` / `app.py` to ground the SQLite-freeze question.

---

## Verdict

**Schema correctness: ✅.** Every shipped table mirrors the spec column-for-column. FK targets resolve. Indexes match. Idempotency works. The Rule #9 anchor checks in the handoff are genuine.

**Process: 🟡 one unilateral spec override (SQLite freeze) that should have been a stop-and-ask.** Three smaller drift items.

---

## What was verified

### Spec mirror — line-by-line cross-read against Integration v3

| Table | Spec section | Cols match | UNIQUE match | Indexes match |
|---|---|---|---|---|
| `provider_auth` | §4.1 (14 cols) | ✅ | ✅ `(user_id, provider)` | ✅ partial `WHERE status IN ('error', 'pending_backfill')` |
| `webhook_events` | §4.2 (11 cols) | ✅ | n/a | ✅ both — lookup composite + partial `WHERE processed_at IS NULL` |
| `polar_sleep` | §5.1 | ✅ | ✅ `(user_id, date)` | n/a |
| `polar_nightly_recharge` | §5.1 | ✅ | ✅ `(user_id, date)` | n/a |
| `polar_cardio_load` | §5.1 | ✅ | ✅ `(user_id, date)` | n/a |
| `polar_continuous_hr_samples` | §5.1 | ✅ | ✅ `(user_id, timestamp_ms)` | ✅ `idx_polar_hr_user_time` |
| `wahoo_plans` | §5.2 | ✅ | n/a (outbound log) | ✅ `idx_wahoo_plans_plan_item` |
| `coros_daily_summary` | §5.3 | ✅ | ✅ `(user_id, happen_day)` | n/a |
| `coros_hrv_samples` | §5.3 | ✅ | ✅ `(user_id, timestamp_s)` | n/a |
| `coros_plans` | §5.3 | ✅ | n/a (outbound log) | ✅ `idx_coros_plans_plan_item` |
| `cardio_log` ALTERs ×4 | §6 | ✅ | n/a | n/a |
| `training_log` ALTERs ×3 | §6 | ✅ | n/a | n/a |

FK targets `users(id)` and `plan_items(id)` exist in both `_SQLITE_MIGRATIONS` and `_PG_MIGRATIONS` blocks (`plan_items` defined at `init_db.py:150` SQLite / `:368` PG). No dangling FKs.

PG block uses `payload TEXT` (not JSONB) per spec §4.2 portability note — verified.

### Idempotency claim

The SQLite block uses `CREATE TABLE IF NOT EXISTS` on CREATEs. The ALTERs are bare (`ADD COLUMN` without `IF NOT EXISTS` — SQLite doesn't support it) but the migration loop's `try/except` covers re-runs. The PG block uses `IF NOT EXISTS` on both CREATEs and ALTERs (PG-specific syntax). Re-run safety is real.

### Backlog v14 + DATABASE.md

Backlog row D-50 correctly updated to 🟡 Partial — schema ✅, wiring pending. v14 header documents the bump. DATABASE.md (root) §"Provider integrations" landed between Garmin and Shared catalogs as advertised.

---

## Findings

### 1. SQLite migrations shipped despite a locked freeze (most important)

`Athlete_Data_Integration_Spec_v3.md` §2.5 line 118, confirmed 2026-05-13:

> *"Integration table CREATE statements use PG types directly. No SQLite variants are specified. The `_SQLITE_MIGRATIONS` list in `init_db.py` is frozen — no new entries — and eventually removed as part of the Option A migration."*

Backlog `D-54` re-states it: *"`_SQLITE_MIGRATIONS` frozen — no new entries."*

The ship added **+147 lines + 7 ALTERs to `_SQLITE_MIGRATIONS`** plus the +146-line PG mirror, in direct contradiction.

The handoff acknowledges this in §8 as the "best argument against this session's scope" and overrides on dev-experience grounds. Per CLAUDE.md stop-and-ask triggers #5 (schema changes affecting an inter-layer contract) and #8 (architectural alternatives — don't pick silently), this was Andy's call to make, not the implementer's. The override may be the right call — it's a reasonable argument — but the process bypassed the trigger list.

**Grounded recommendation (not a rollback):**

Runtime audit of `init_db.py:2289` + `database.py:88` + `app.py:52` confirms: `init_sqlite()` only fires when `DATABASE_URL` is unset. If you develop against Neon directly (with `DATABASE_URL` set), `_SQLITE_MIGRATIONS` is **inert** — the new 147 lines never execute against any database you touch. They cost nothing operationally.

What needs to "stay in sync" for the eventual D-54 swap: **nothing on the schema side.** The collapse just deletes `_SQLITE_MIGRATIONS`, the `SQLITE_SCHEMA` string, `init_sqlite()`, the `else` branch in `database.py:get_db`, the `sqlite_path()` helper, the dual-type strategy in DATABASE.md, and the `sqlite3` imports. No SQLite-side state needs to match PG-side state for the collapse to work — the SQLite path just stops being chosen.

**Three options:**

- **A. Ratify retroactively, leave the lines, harden the freeze going forward.** Lowest cost. Acknowledge §2.5 was broken once; reaffirm the rule for future schema additions. The 147 lines are sunk cost; ripping them out is a separate PR with no operational benefit (they don't execute for you). Add a one-line carve-out to §2.5 noting D-50 Phase 1 SQLite block ships as a documented exception.

- **B. Bring D-54 forward.** Skip the freeze-rule maintenance entirely. One PR deletes `_SQLITE_MIGRATIONS` + `SQLITE_SCHEMA` + `init_sqlite()` + the SQLite branches in `database.py` + the dual-type docs in DATABASE.md. Estimated ~150–300 lines deleted across 4 files. Not blocked by anything (no SQLite users; Catalog Migration Phase 5 is logically separate — it removes `public.*` → `layer0.*` references, not the SQLite path). The risk is scope creep into the catalog migration; isolate to backend collapse.

- **C. Roll back just the D-50 SQLite block.** Highest cost-to-benefit. Honors the spec literally but creates churn in a path nobody uses.

Recommend **A or B**, with **B** if you want to stop accumulating freeze-rule debt. **A** if you'd rather lock the rule in and revisit D-54 on its own schedule.

### 2. `init_db.py` line count under-stated

§3 row 1 says "+~170 lines"; actual is **+293** (SQLite ~147 + PG ~146). Rule #10 expects on-disk reality. Looks like a single-block estimate that wasn't updated when the PG mirror was added. Not a correctness issue — flagging because Rule #10 verification should catch this kind of arithmetic drift.

### 3. `DATABASE.md` path is ambiguous

§3 row 2 just says `DATABASE.md`. The file actually edited is **`/DATABASE.md`** (repo root, the v1-app database doc — correct file for this work). But `aidstation-sources/DATABASE.md` also exists; a strict Rule #9 reader anchor-checking `aidstation-sources/DATABASE.md` would see no change and flag false drift. Future handoffs should prefix the path when the same filename exists in multiple directories.

### 4. PG path not exercised; failure mode is silent

The handoff acknowledges this in §5. Worth re-emphasizing: the migration loop's `try/except` swallows malformed statements without surfacing. The `wellness_self_report` precedent doesn't prove syntactic validity for *these* tables — only that the pattern works for *some* table. Monitor Neon `init_postgres()` cold-start logs after deploy. Specific things to watch: `SERIAL` + `REFERENCES` ordering, `BIGINT` defaults, partial-index `WHERE` clauses, the cast-free `provider_user_id TEXT` joins.

---

## Smaller items (factual, not corrective)

- **`webhook_events` retention prune** not implemented. Spec §4.2 calls for daily prune of `processed_at IS NOT NULL AND received_at < NOW() - INTERVAL '90 days'`. Handoff §8 flags it but it should be a real backlog row, not just a §8 mention. Promote to a tracked D-NN.
- **`session_blob` column ships unused** until Garmin (D-55) reopens. Architecturally clean per spec §2.3; one NULL TEXT column per `provider_auth` row.
- **`garmin_auth → provider_auth` cleanup not pre-staged.** Correctly deferred to D-55 when Garmin API reopens. Worth a backlog hook so the eventual D-55 PR remembers to `DROP TABLE garmin_auth` in both migration lists (or just `_PG_MIGRATIONS` if D-54 has landed by then).
- **Strava `cardio_log.strava_activity_id`** correctly deferred per spec §6 + D-48.

---

## What the handoff got right

- **Genuine Rule #9 verification.** The anchor-check table at the top is real — I re-ran the checks and confirmed.
- **Spec mirror is faithful.** Every column, every UNIQUE, every index matches Integration v3 §4–§6 verbatim. The PG-vs-SQLite type translations (TIMESTAMP↔TEXT, BIGINT↔INTEGER, BOOLEAN↔INTEGER) are correct and documented in inline comments.
- **5-file ceiling respected.** Four substantive files; well under the cap.
- **Idempotent re-run actually tested.** Captured in §5 with column lists and index lists.
- **Mechanically-applicable forward instructions in §6.** Next-session reading list begins with CLAUDE.md per Rule #13. Wiring-PR breakdown in §6.2 is concrete (helper module → shipped providers → stubs → webhook handlers → Garmin).
- **§8 gut check is honest.** Acknowledges PG-path not exercised, `session_blob` dead weight, zero test coverage, and (correctly) frames the SQLite-freeze override as the "best argument against this session's scope." The override itself was wrong-process; recognizing it openly is the right behavior.

---

## Recommended next moves

1. **Decide on Finding #1** — A (ratify + reaffirm freeze), B (bring D-54 forward as its own track), or C (roll back D-50 SQLite block).
2. **Add a backlog row for `webhook_events` retention prune** so it doesn't get forgotten when wiring lands.
3. **Watch Neon logs on next deploy** for `_PG_MIGRATIONS` exceptions — the migration loop swallows them, so a malformed statement would fail silently until something queried a missing table.
4. **Reaffirm stop-and-ask trigger discipline** in the next session's kickoff. The override here wasn't catastrophic (the SQLite block is inert for Andy's dev path), but the same pattern applied to a non-inert decision would be.

---

*End of D-50 Phase 1 Schema review.*
