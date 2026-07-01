# V5 Implementation — T-5.7/#754 (real-DB cardio-ingest test) — WS-5 closed — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-5.4/T-5.5/T-5.6 (Komoot blocked, Wahoo plan.json push, Karoo labeling — merged into `main` via PR #1124 before this session started).
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 T-5.7
**Predecessor handoff:** [`V5_Implementation_T54_KomootBlocked_T55_WahooPlanExport_T56_KarooLabeling_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T54_KomootBlocked_T55_WahooPlanExport_T56_KarooLabeling_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/project-handoff-execution-cijxz8` — no PR opened yet (project rule: commit + push + bookkeep, wait for Andy's explicit go).
**Status:** T-5.7 shipped. **WS-5 (Integrations) is now fully closed** — every task DONE or BLOCKED-ON-PARTNER. Suite: **4169 passed / 49 skipped, 0 failed** (+19 skipped, 0 changed passed-count).

---

## 1. Session-start verification (Rule #9)

`bash aidstation-sources/scripts/verify-handoff.sh` — all ✅ except one expected non-issue: `tests/test_cardio_ingest.py` flagged missing, but that file is T-5.7's own *next-step* pointer text in the predecessor handoff (not something it claimed already existed) — a false positive of the script's naive path-scan, not drift. Every other claimed file/anchor spot-checked directly (`to_wahoo_plan_json`, `push_session`, `_WAHOO_SCOPES`/`_WAHOO_SCOPE_VERSION`, the Wahoo/Karoo template strings, `TestWahooPlanJson`/`TestPush`) — all present. PR #1124 (that session's work) was already merged into `main`; this session's branch tip was `origin/main` (`git log origin/main..HEAD` = 0 commits), so no branch restart was needed.

## 2. What shipped

### T-5.7/#754 — Real-DB cardio-ingest test — **DONE**

The predecessor handoff's own recipe: the container has a local `postgres:16` cluster installed (stopped by default) that could serve as the dev-side integration-test target, since `layer0-gate`'s CI Postgres service only loads a narrow `layer0`-only genesis snapshot — not the full app schema (`cardio_log`, `provider_raw_record`, etc.) `_bulk_insert_cardio`/`_record_provider_raw_cardio` need.

**What changed:**
- Started the local cluster (`service postgresql start`), created a scratch `aidstation_test` database, confirmed `init_db.init_postgres()` bootstraps it correctly (the full schema + all `_PG_MIGRATIONS`, including the per-source `cardio_log` columns and their partial UNIQUE indexes — verified via `\d cardio_log` that `coros_label_id`/`wahoo_workout_id`/`polar_exercise_id`/`strava_activity_id`/`rwgps_trip_id` and their `*_uidx` partial unique indexes, plus `discipline_id`/`started_at`/`cluster_id`, all land). A handful of legacy migrations fail-and-skip on a from-scratch bootstrap (pre-existing best-effort behavior, e.g. a since-superseded `DROP CONSTRAINT`/column-rename step) — expected, not introduced by this session, and `init_postgres()` already tolerates it per-statement (Rule #15 logging).
- **`tests/conftest.py`** — new `requires_real_postgres` skipif marker, mirroring `requires_anthropic_api_key`'s existing pattern exactly: gated on a `TEST_DATABASE_URL` env var, so the default `pytest tests/` run stays $0/side-effect-free and the new file collects-but-skips unless a developer points the var at a scratch Postgres.
- **`tests/test_cardio_ingest.py`** (new) — real-DB tests for `_bulk_insert_cardio` / `_record_provider_raw_cardio` / `_already_imported`, run against the real bootstrapped schema via `database._PgConn` wrapping a real `psycopg2` connection (not a fake connection that just records SQL strings). Each test gets its own connection + throwaway user row, and is rolled back (never committed) at teardown — no truncation logic needed, no cross-test leakage. 19 tests:
  - gid lands in the right per-source column across all 5 sources (garmin/coros/wahoo/polar/strava).
  - `provider_raw_record` is tagged with the true upload source (not the parser's default) and **upserts, not duplicates**, on a second write for the same external_id — proving the `ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE` arbiter actually matches the table's real unique constraint (the exact bug class T-5.7's own motivating issue calls out: an arbiter mismatch is invisible to a fake connection that never sends the statement to a real server).
  - the **exact #752 regression class**: a blank `observed_at` string (the parser's fallback when a FIT's session timestamp doesn't parse) stores `NULL` rather than raising `psycopg2.errors.InvalidDatetimeFormat` — this time against a real server, not a mock.
  - the partial UNIQUE index each of coros/wahoo/polar/strava has on `(user_id, <col>)` really exists, raises `UniqueViolation` on a same-user duplicate `gid`, and is correctly scoped per-user (two different users can reuse the same external id without colliding).
  - `_already_imported` — the caller-side dedup guard `garmin` relies on (it has no DB-level unique index; the plan's own ground-truth notes this is the historical default path) — is scoped to the authenticated user only, using a real Flask request context + session (matching how the actual route calls it).

**Deliberately NOT done:**
- **No CI job wired this session.** The predecessor handoff explicitly flagged "decide then whether to also wire a CI job in the same PR or file that as a fast-follow" — filed as [#1125](https://github.com/ahorn885/exercise/issues/1125) rather than building it here: `layer0-gate`'s existing Postgres `services:` block in `.github/workflows/ci.yml` isn't reusable as-is (it loads a `layer0`-only snapshot, not the full app schema), so standing up the right CI shape is its own scoped piece, not a T-5.7 sub-step. Today the test is locally-runnable on demand (`TEST_DATABASE_URL=... pytest tests/test_cardio_ingest.py`), not yet CI-gating.
- No changes to `_bulk_insert_cardio`/`_record_provider_raw_cardio`/`_already_imported` themselves — this task is a test-only addition per the plan's own scope (verify existing behavior against real SQL, not change it).
- No `_bulk_insert_strength` coverage — the plan's stated T-5.7 scope is cardio only ("`_bulk_insert_cardio` + dedup + provider_raw across all sources").

## 3. Tests

Full suite: **4169 passed / 49 skipped, 0 failed** (baseline 4169 passed / 30 skipped — 0 change to the passing count, +19 skipped: the new file collects but skips by default). Ran `tests/test_cardio_ingest.py` standalone against `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aidstation_test` — **19 passed**, confirming the real-DB path actually works, not just that it's correctly gated off. `ruff check tests/test_cardio_ingest.py tests/conftest.py` — **0 findings**.

## 4. Docs updated (this session)

- `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` — T-5.7 flipped to **DONE**, with an as-built note; §4 Global order updated to mark WS-5 fully closed; §5 Bookkeeping records the #1125 fast-follow filing.
- `CURRENT_STATE.md` — new "Last shipped session" entry; prior top entry (T-5.4/T-5.5/T-5.6) demoted to a named predecessor entry.

## 5. GitHub bookkeeping (this session)

- **#754 — commented + closed** (`completed`): what shipped + the #1125 fast-follow pointer.
- **#1125 — filed** (new issue): the CI-wiring fast-follow — set `TEST_DATABASE_URL` in a CI job and actually run `tests/test_cardio_ingest.py` automatically. `priority:low`, `when:later`, `infra-ops`.
- Plan doc updated in-place per above (exempt from the 5-file ceiling as bookkeeping).

## 6. Next session pointers

Per the execution plan's §4 Global order, **WS-5 is now fully closed** (T-5.1 through T-5.7 all DONE or BLOCKED-ON-PARTNER). Every remaining open task in the plan is Andy-gated:

- **T-1.4 (#930)** — GATE: Andy ratifies the one-sided taper anchor wording before merge. Must land before T-1.5 (R3).
- **WS-2 (#297/#299/#301/#302/#306 + #305)** — GATE: Andy ratifies the render-vs-trim disposition table (plan §3) before any code.
- **T-3.2 (#831)** — GATE: Andy confirms the saturation-cap rule matches `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md`.
- **T-3.3 (#559)** — GATE: the Layer-0 migration needs Andy's one-tap `layer0-apply` approval.
- **[#1125](https://github.com/ahorn885/exercise/issues/1125)** (this session's fast-follow) — ungated, but scoped as its own small CI-infra task, not folded in here.

There is no fully-ungated plan task left to pick up on its own — the next session needs one of Andy's ratifications (T-1.4's wording, WS-2's render/trim table, T-3.2's saturation-cap confirmation, or T-3.3's Layer-0 migration approval) to keep moving through the plan, or can pick up #1125 (CI wiring) as an ungated, self-contained piece.

**No PR opened this session** (project rule: commit + push + bookkeep, wait for Andy's go). Once he says go: push (already done), open the PR (ready, not draft, merge-commit method), `enable_pr_auto_merge`.

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `bash aidstation-sources/scripts/verify-handoff.sh`

---

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Real-Postgres skip marker | `tests/conftest.py` | `requires_real_postgres`; `TEST_DATABASE_URL_ENV` |
| Real-DB ingest tests | `tests/test_cardio_ingest.py` | `class TestBulkInsertCardioAcrossSources`; `class TestEmptyObservedAtCoercesNull`; `class TestProviderRawUpsertOnConflict`; `class TestDedupUniqueIndexEnforced`; `class TestAlreadyImported` |
| Suite (default, no real DB) | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4169 passed / 49 skipped |
| Suite (real DB, standalone) | — | `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aidstation_test /tmp/venv/bin/python -m pytest tests/test_cardio_ingest.py -q` → 19 passed |
| Lint | — | `ruff check tests/test_cardio_ingest.py tests/conftest.py` → 0 findings |
| Plan doc | `plans/PlanGenReliability_..._v1.md` | T-5.7 shows "DONE 2026-07-01"; §4 shows "WS-5 fully closed" |
| GitHub | — | #754 closed `completed`; #1125 filed (CI-wiring fast-follow) |
| Branch | — | `claude/project-handoff-execution-cijxz8`; no PR yet, awaiting Andy's go |

**End of handoff.**
