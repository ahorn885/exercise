# V5 Implementation — `primary_movement` applied to prod + Ops automation buildout — Closing Handoff

**Date:** 2026-06-15
**Branch:** `claude/intelligent-euler-hjggno` (this session's PRs all merged to `main`).
**Predecessor handoff:** `V5_Implementation_Layer0_PrimaryMovementBackfill_0006_2026_06_15_Closing_Handoff_v1.md` (the `0006` build + the bug, PR #615).
**Theme:** close out the `primary_movement` fix in prod, then stand up "decide-not-do" automation so prod DB ops + merges run in the cloud (Andy is mobile / device-changing; only consistent access is Claude Code web/Android).

---

## 1. `primary_movement` — fully closed in prod

- **#615** (`0006` migration + `validate_layer0` `primary_movement` guard) merged to `main`.
- **Andy applied `0006` to prod Neon** (via the Neon SQL editor first, then re-applied through the new gated workflow as a no-op). **Verified via the read-only diagnostics workflow:** 24 active disciplines, **0 NULL**, all at `0A-v1.6.8`, distribution = the canon (running 4 / cycling 5 / hiking 2 / swimming 1 / paddling 5 / climbing 4 / skiing 3). Live Layer 2E nutrition is movement-aware again.
- **Baseline re-dumped → `etl/output/layer0_etl_v1.8.0.sql`** (**#626**, gate-validated: loads v1.8.0 → applies `0006` no-op → `validate_layer0` green). The committed baseline no longer lags live — closes the drift class that caused the bug. (v1.7.0 left in place but inert; all consumers pick newest by version.)
- **#616** (the tracking bug) closed completed.

## 2. Ops automation shipped (the "decide-not-do" setup)

Andy chose (via `AskUserQuestion`, multi-select) to stand up all four. Principle: anything that needed his local machine moves into a cloud workflow Claude triggers; he only **approves prod writes** (one tap).

| PR | What | Setup Andy did |
|---|---|---|
| #617 | `.claude/settings.json` SessionStart `git pull --ff-only` hook (local clones auto-sync) | — |
| #625 | `layer0-redump.yml` — `pg_dump` live → `layer0_etl_v<ver>.sql`, pushes a branch | `NEON_DATABASE_URL` secret |
| #627 | `layer0-apply.yml` (apply migrations to prod, gated by `production` env) + `neon-query.yml` (read-only diagnostics) | `production` environment w/ himself as required reviewer, **bypass off**; `NEON_RO_DATABASE_URL` secret (read-only Neon role) |
| #628 | `.github/CODEOWNERS` soft-nudge on `etl/migrations/` | auto-merge enabled + branch protection (required checks, **0 approvals**, admin-bypass off) |
| this PR | `layer0-validate-live.yml` (nightly `validate_layer0` vs live prod via RO role) + this bookkeeping/handoff | — |

**All four test-fired green this session:**
- `neon-query` ran a read-only SELECT → returned the live distribution (RO role + secret + read-only enforcement confirmed).
- `layer0-apply` parked at `waiting` → Andy approved → applied `0006` no-op → success (the `production` approval gate works end-to-end).
- Auto-merge: #628's merge was correctly **blocked** by branch protection while checks ran, then auto-merged itself on green (the self-land flow works).
- `DIAG_TOKEN` rotated; with it, Claude reads prod logs via `GET /admin/logs?token=` (WebFetch) — Rule #14 without "paste me the traceback."

## 3. Correction (faithful reporting)

I raised a **false alarm** that the `DIAG_TOKEN` value was committed in `CURRENT_STATE.md` + the plan doc. A precise base64-signature search came back empty — both docs use the `<DIAG_TOKEN>` **placeholder**; the first scan's hit was a greedy regex matching ordinary 12+ char words after "token" (e.g. "reachability"). Nothing was leaked; Andy rotated anyway as harmless hygiene.

## 4. How Claude operates now (for next session)

- **Open PR → `enable_pr_auto_merge` (SQUASH) → it self-lands on green.** Don't merge mid-run (branch protection enforces required checks: `Python unit suite (stubbed)`, `JS harness (jsdom)`, `Layer 0 integrity gate`).
- **Apply a Layer 0 migration to prod:** trigger `layer0-apply.yml` (`actions_run_trigger`); it waits for Andy's `production` approval; he taps approve.
- **Refresh the baseline:** trigger `layer0-redump.yml` (input `version`), then open the PR from the pushed branch so the gate validates it.
- **Investigate prod data:** trigger `neon-query.yml` with a SELECT; read the result from the job log.
- **Read prod logs:** Andy pastes the current `DIAG_TOKEN` (chat-only, never commit) → WebFetch `…/admin/logs?token=…`.

## 5. Owed / next

- ⬜ **STILL OWED (carried, unrelated):** the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14) — now easier with the rotated token + log access.
- New functionality (off-plan): **#592** race-location terrain/weather; **#593** reduced-volume travel days. Larger v2 tracks: determinism-first plan-gen epic **#427/#428/#429**, **#316** latency.
- Nothing is owed on the `primary_movement` arc or the automation buildout — both fully closed + verified.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — the `primary_movement` ✅ bullet + the ops-capabilities note. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Baseline refreshed | `etl/output/layer0_etl_v1.8.0.sql` | present; `CREATE SCHEMA layer0`; active disciplines carry `primary_movement` |
| Apply workflow | `.github/workflows/layer0-apply.yml` | `environment: production`; `etl/migrations/layer0/*.sql` loop |
| Redump workflow | `.github/workflows/layer0-redump.yml` | `pg_dump --schema=layer0`; pushes branch |
| Diag query workflow | `.github/workflows/neon-query.yml` | `NEON_RO_DATABASE_URL`; `default_transaction_read_only=on` |
| Validate-live workflow | `.github/workflows/layer0-validate-live.yml` | `cron: "0 7 * * *"`; `python -m etl.layer0.validate_layer0`; `DATABASE_URL: ${{ secrets.NEON_RO_DATABASE_URL }}` |
| CODEOWNERS | `.github/CODEOWNERS` | `/etl/migrations/ @ahorn885` (soft) |
| Session hook | `.claude/settings.json` | `SessionStart` → `git pull --ff-only \|\| true` |
| Bookkeeping | `aidstation-sources/CURRENT_STATE.md` | top entry = `primary_movement` DONE/applied + ops automation |
| Owed | — | nothing on this arc; T3-refresh re-verify carried |
