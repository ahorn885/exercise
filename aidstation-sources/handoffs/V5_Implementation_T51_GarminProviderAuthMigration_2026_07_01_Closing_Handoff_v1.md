# V5 Implementation — T-5.1/#249: Garmin → shared `provider_auth` — Closing Handoff (2026-07-01)

**Session:** Continuation of `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` §4 Global order, after T-1.3/T-3.4 (PR #1121, merged). Every other ready-to-build item (T-1.4, WS-2, T-3.2, T-3.3) is Andy-gated, so the only fully-ungated next task was WS-5's T-5.1.
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 T-5.1
**Predecessor handoff:** [`V5_Implementation_T13_HITLSpecFix_T34_573FailoverStrengthRefresh_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_T13_HITLSpecFix_T34_573FailoverStrengthRefresh_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/v5-implementation-closing-m65gz8` — PR [#1122](https://github.com/ahorn885/exercise/pull/1122) opened per Andy's go; auto-merge armed (merge-commit method, lands once required checks pass).
**Status:** T-5.1 shipped as one working-tree change (3 substantive code files: `garmin_connect.py`, `routes/garmin.py`, `routes/admin.py` — within the 5-file ceiling). Suite: **4137 passed / 30 skipped, 0 failed** (+8).

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` — all ✅ (predecessor's claimed files all exist on disk; the predecessor's own §6 anchors were spot-checked directly: `grep -c "escalate to next-run HITL gate" Layer4_Spec.md` → 0, `include_grid_tag` present in `per_phase.py`/`plan_refresh_t1.py`/`plan_refresh_t3.py`, `strength_substitution` present in `payload.py`). Confirmed the predecessor's branch (`claude/orphaned-data-partial-wiring-87rdt7`) had since been merged as **PR #1121** — `origin/main` and this session's branch tip were identical (`git merge-base --is-ancestor origin/main HEAD` true), so no reconciliation was needed; the predecessor handoff's "not yet pushed" note was simply stale by the time this session started (Andy had since said go).

## 2. What shipped

### Conflict caught before writing code (Trigger-adjacent — surfaced, not built past)

The plan lists **T-5.1** as `GATE: none` — "fully independent, no plan-gen coupling." But the actual GitHub issue it closes, **#249**, is labeled `status:blocked` with body text: *"Currently paused because Garmin's API is closed... Blocked — PAUSED on Garmin's closed API."* Neither the plan's ground-truth section nor its task text mentioned this. Digging further, `PROVIDERS_SCHEMA.md`/`DATABASE.md` both explicitly recorded the *design decision* to wait: "when Garmin API access reopens... Garmin migrates to `provider_auth`... Until the API reopens, `garmin_auth` stays in `init_db.py` as-is."

This is a real conflict between the plan doc and both the live issue tracker and the design docs, not a stale-issue-text situation the plan's own §1 "Ground truth" section could wave off. Rather than pick a reading silently, asked Andy (`AskUserQuestion`): proceed anyway, do the next WS-5 tasks instead, or hold off. **Andy: proceed with T-5.1.** Rationale surfaced before he decided: Garmin's `garth` login is an unofficial session-based library, not OAuth — the "API closed" blocker is about official developer/OAuth access, which this storage-only migration never touches.

### The migration itself

`routes/provider_auth.py` needed **no changes** — `session_blob` was already a reserved column for exactly this (confirmed via `PROVIDERS_SCHEMA.md`'s own design note), and `_UPSERTABLE_COLUMNS` already includes it.

**`garmin_connect.py`** — all 4 read/write sites now go through `routes.provider_auth` (aliased `pa`):
- `_save_session_to_db(db, username='')` — was SELECT-then-branch UPDATE/INSERT against `garmin_auth`; now one `pa.upsert_auth(db, current_user_id(), 'garmin', session_blob=session_json, provider_user_id=username, status=pa.STATUS_ACTIVE)` call (upsert handles its own commit).
- `_load_client(db)` — `pa.get_auth(db, current_user_id(), 'garmin')`, reads `row['session_blob']` instead of `row['garth_session']`.
- `get_auth_status(db)` — same swap; `provider_user_id` replaces `garmin_username` as the surfaced username.
- `fetch_activities(db, start, end)` — same swap for the browser-cookie-auth branch's session lookup.

**`routes/garmin.py`** — the two endpoints that bypassed `garmin_connect.py` with their own direct SQL (missed by a plan file-list that didn't call them out individually, but covered since the task's file list did name `routes/garmin.py`):
- `auth_import_cookies` — collapsed the SELECT-then-branch UPDATE/INSERT to one `pa.upsert_auth(...)` call.
- `auth_import_tokens` — same collapse; also dropped an already-dead import (`_save_session_to_db` was imported but never called in the original code).

**`routes/admin.py`** — `_delete_user_and_data`'s cascade-delete chain gained `DELETE FROM provider_auth WHERE user_id = ?`. This table was **never in the cascade for any provider** (Strava/Whoop/Wahoo/Polar/COROS/RWGPS/Oura all write there too) — a pre-existing gap, not introduced by this session, but this migration is what exposed it: without this line, deleting a Garmin-connected user's account would now hit an FK violation (`provider_auth.user_id REFERENCES users(id)`, no `ON DELETE CASCADE`) where it previously worked (the old `garmin_auth` DELETE line is still there and still harmless, but no longer does anything load-bearing). Added as a general `DELETE FROM provider_auth` (all providers), not scoped to just `provider = 'garmin'`, since the same gap affects every other provider identically and there's no reason to fix it only for the one this session touched.

### Data migration — none needed

Triggered the read-only `neon-query.yml` GitHub Action (`SELECT count(*) AS n, count(garth_session) AS with_session FROM garmin_auth`) against prod: **0 rows**. Matches `PROVIDERS_SCHEMA.md`'s own note ("no production data and no Garmin-connected users to preserve"), now confirmed live rather than assumed. No backfill script needed.

### What was deliberately NOT done

- **Did not drop the `garmin_auth` table.** The plan's step only asked for a conditional data migration ("if needed" — resolved to not-needed), not a DROP. Public-schema `_PG_MIGRATIONS` auto-apply on every Vercel deploy with no gate (unlike the Andy-gated `layer0-apply`), so an irreversible DROP TABLE deserves its own explicit go, not to ride along with an auth-storage refactor. The table is now empty and unused; flagged as a follow-up, not built.
- **Did not touch any other provider.**

## 3. Tests

New `tests/test_garmin_provider_auth_migration.py` (8 tests):
- `TestGarminConnectStorageMigration` (5): round-trip save/load through `provider_auth`; unauthenticated-when-no-row; `_load_client` raises without a saved session; **the plan's stated verify** — two users' Garmin sessions never cross (built against a fake DB that implements the real `upsert_auth`/`get_auth` SQL shapes — parsed from the actual query strings via the real column list — rather than mocking the helpers away, so isolation is proven against the production query, not a stand-in); `fetch_activities`'s browser-auth path reads the correct per-user session.
- `TestGarminAuthImportRoutes` (2): `auth_import_cookies` and `auth_import_tokens` each call `provider_auth.upsert_auth` scoped to the requesting session's `user_id`, provider `'garmin'`.
- `TestAdminCascadeDelete` (1): `_delete_user_and_data` now issues a `DELETE FROM provider_auth` alongside the legacy `garmin_auth` line.

Full suite: **4137 passed / 30 skipped, 0 failed** (baseline 4129 + 8 new, 0 removed/changed). Also spot-ran the pre-existing render suites that reference `garth_session`/`garmin_username` fake-DB shapes (`test_redesign_connections_render.py`, `test_redesign_profile_render.py`, `test_redesign_garmin_import_render.py`, `test_redesign_garmin_wellness_log_render.py`, `test_garmin_bulk_source.py`, `test_garmin_fit_parser_strength.py`) — 134 passed, no regressions (their fake rows' leftover `garth_session`/`garmin_username` keys are generic catch-all fallback fields for several unrelated queries, not specific to this migration, and were left as-is).

## 4. Docs updated (this session)

- `PROVIDERS_SCHEMA.md` §5.1 + §7 — replaced the "wait for API reopen" plan language with what actually shipped, including the neon-query 0-rows confirmation and the not-yet-dropped-table note.
- `DATABASE.md` — `garmin_auth` entry marked retired; `provider_auth` entry updated to include Garmin; the table-usage xref table's `garmin_auth` row updated, `provider_auth` row added; `garmin_connect.py` narrative section + the admin-delete cascade list updated.
- `HANDOFF.md` — the parked "Garmin per-user OAuth" item's table reference updated (`garmin_auth` → `provider_auth`; the underlying `/tmp/garth_session` process-shared-cache bug, #284, is unchanged and still parked).

## 5. GitHub bookkeeping (this session)

- **#249 — commented + closed** (`completed`): storage migration shipped; noted the `status:blocked` label was about the official OAuth API, not the garth session-storage layer, and that Andy explicitly ratified proceeding despite the label.
- **#284 — commented, left OPEN** (icebox, unaffected): the shared `/tmp/garth_session` process-cache-across-users bug is a separate problem from where the DB row lives; not touched or fixed by this migration.
- **#757 — commented** (already closed `completed` from its own session): noted its residual follow-up (`connected_providers` not surfacing Garmin) is now resolved as a side effect of this migration, no code change needed there since `q_layer3A_connected_providers` was already provider-agnostic.
- Plan doc updated in-place: T-5.1 flipped to **DONE** with an as-built note (the #249-label conflict + resolution, the `routes/admin.py` addition beyond the literal file list, the no-backfill-needed confirmation).

## 6. Next session pointers

Per the execution plan's §4 Global order, WS-5 continues:

- **T-5.2 (#1092) — TCX/GPX single-file ingest route.** Ungated. `tcx_gpx_parser.py` already returns the normalized cardio dict; add the upload route.
- **T-5.3 (#1093) — Wahoo full FIT stream.** Ungated. Reuse `garmin_fit_parser.parse_fit()` directly (do not extract a shared parser).
- Everything outside WS-5 stays exactly as the predecessor handoff left it: **T-1.4 (#930)** GATED on Andy ratifying taper anchor wording; **WS-2** GATED on the render-vs-trim table; **T-3.2/T-3.3** GATED (saturation-cap rule / Layer-0 migration).
- **PR [#1122](https://github.com/ahorn885/exercise/pull/1122) opened** per Andy's go; auto-merge armed (merge-commit method) — lands once required checks pass.
- **Follow-up flagged, not built:** dropping the now-empty, now-unused `garmin_auth` table (a public-schema DDL that auto-applies with no gate — deserves an explicit go, not a ride-along).

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`
6. `./scripts/verify-handoff.sh`

---

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Storage swap | `garmin_connect.py` | `from routes import provider_auth as pa`; `pa.upsert_auth(` / `pa.get_auth(` at all 4 former `garmin_auth` sites; `grep -c garmin_auth garmin_connect.py` → 0 |
| Route swap | `routes/garmin.py` | `pa.upsert_auth(` in `auth_import_cookies` + `auth_import_tokens`; `grep -c garmin_auth\b routes/garmin.py` → 0 |
| Cascade fix | `routes/admin.py` | `DELETE FROM provider_auth                 WHERE user_id = ?` in `_delete_user_and_data` |
| Neon check | — | `neon-query` run `28494609221`: `SELECT count(*), count(garth_session) FROM garmin_auth` → `0, 0` |
| Docs | `PROVIDERS_SCHEMA.md` / `DATABASE.md` / `HANDOFF.md` | "wait for API reopen" language replaced with "DONE 2026-07-01, T-5.1/#249" |
| Tests | `tests/test_garmin_provider_auth_migration.py` | `TestGarminConnectStorageMigration::test_two_users_garmin_sessions_never_cross` (the plan's stated verify) |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 4137 passed / 30 skipped |
| GitHub | — | #249 closed `completed`; #284 commented (unaffected, left open); #757 commented (residual resolved); plan doc T-5.1 flipped to DONE in-place |
| Branch | — | `claude/v5-implementation-closing-m65gz8`; PR [#1122](https://github.com/ahorn885/exercise/pull/1122), auto-merge armed |

**End of handoff.**
