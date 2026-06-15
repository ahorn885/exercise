# V5 Implementation — Ops automation operating-model codified (session close) — Closing Handoff

**Date:** 2026-06-15
**Branch:** `claude/intelligent-euler-hjggno` (all this session's PRs merged to `main`).
**Predecessor handoffs (same session, detailed sub-records):**
- `V5_Implementation_Layer0_PrimaryMovementBackfill_0006_2026_06_15_Closing_Handoff_v1.md` (the bug + `0006` build, PR #615)
- `V5_Implementation_Layer0_PrimaryMovement_Applied_OpsAutomation_2026_06_15_Closing_Handoff_v1.md` (apply-to-prod + automation buildout)
- **This handoff** = the definitive session close: the operating model is now **codified into the durable docs** (`CLAUDE.md` + `CARRY_FORWARD.md`) and the live-validate guard is verified.

---

## 1. What this session delivered (end to end)

**A. Layer 0 `primary_movement` — fixed, applied to prod, verified, baseline re-synced.**
- Found a real prod gap: all 24 active `layer0.disciplines` rows had `primary_movement` NULL → Layer 2E nutrition was movement-blind. Root cause: a full ETL re-extraction clobbers the column (the canon normalizer stamps `endurance_profile` but not `primary_movement`); the old `etl/sources` migration was stale (pre-drift keyspace) and would have failed.
- Fixed via `etl/migrations/layer0/0006_*` (serving-relevant Shape-2 backfill at `0A-v1.6.8`) + a standing `validate_layer0` `primary_movement` guard (PR #615). **Andy applied it to prod;** verified live: **24 active / 0 NULL / `0A-v1.6.8`**. Baseline re-dumped → `etl/output/layer0_etl_v1.8.0.sql` (PR #626, gate-validated). Issue #616 closed.

**B. "Decide-not-do" ops automation — built, verified, and folded into how we work.** (Record issue #630, closed.) Andy is mobile / device-changing; the only consistent access is Claude Code web/Android. So prod DB ops + merges now run in the cloud, Claude drives them, Andy approves only the irreversible bits.
- `layer0-apply.yml` (gated prod migration apply), `layer0-redump.yml` (baseline refresh), `neon-query.yml` (read-only diagnostics), `layer0-validate-live.yml` (nightly `validate_layer0` vs live). PRs #625/#627/#629.
- Auto-merge + branch protection (required checks, 0 approvals, admin-bypass off) → PRs self-land on green; `.github/CODEOWNERS` soft-nudge (PR #628). Local `.claude/settings.json` git-pull hook (PR #617). `DIAG_TOKEN` rotated → prod logs readable via `GET /admin/logs?token=` (Rule #14).
- **All four capabilities test-fired green this session,** incl. `layer0-validate-live` against live prod → `RESULT: PASS — all checks clean (or waived)` (the read-only role covers every check; no grant gap).

## 2. The operating model now in force (the durable change)

Codified in `CLAUDE.md` → Environment quick-reference → *Ops automation*, and `CARRY_FORWARD.md` → *Ops automation / operating model*. **For the next session, this is the default:**

- **Shipping a change:** open a PR → `enable_pr_auto_merge` (SQUASH) → it self-merges once the 3 required checks pass. **Don't merge mid-run** (branch protection enforces checks; `0` approvals because a solo owner can't self-approve — never require reviews or merges deadlock).
- **Applying a Layer 0 migration to prod:** trigger `layer0-apply.yml` (`actions_run_trigger`) → it waits on the `production` environment → Andy taps approve. (No more Neon-SQL-editor pasting.) Migrations must stay idempotent (re-applied each run).
- **Refreshing the baseline after a prod data change:** trigger `layer0-redump.yml` (input `version`) → open the PR from the pushed branch → the gate validates → auto-merge.
- **Investigating prod data:** trigger `neon-query.yml` with a SELECT → read the result from the job log.
- **Reading prod logs:** Andy pastes the current `DIAG_TOKEN` (chat-only) → WebFetch `…/admin/logs?token=…`.

`CLAUDE.md`'s old "schema migrations stay owed-Andy's-local-hands" framing was **corrected** this session (it's now the gated cloud apply). Flagged here per Rule #13 (operating-framing change).

## 3. GitHub issues

- #616 (the `primary_movement` bug) — closed completed (PR #615).
- #630 — filed + closed completed as the canonical record of the ops-automation buildout (links every PR + the secrets/gates).
- No other open issue was addressed (the log-visibility build already shipped in `routes/logs.py` a prior session). Issue search for log/automation surfaced only unrelated compliance epics.

## 4. Owed / next

- ⬜ **STILL OWED (carried, unrelated):** the post-#572 live **T3 *refresh*** re-verify (Rule #14) — now easier with the rotated `DIAG_TOKEN` + direct log access.
- **Nothing owed** on the `primary_movement` arc or the automation buildout — both fully closed + verified.
- New functionality (off-plan): #592 race-location terrain/weather; #593 reduced-volume travel days. Larger v2 tracks: determinism-first plan-gen epic #427/#428/#429; #316 plan-gen latency.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules **+ the new Environment → Ops automation reference**. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — the *Ops automation / operating model* section (now first) + the ✅ `primary_movement` bullet. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Operating model (rules) | `aidstation-sources/CLAUDE.md` | Environment quick-ref has **Ops automation** block; Neon line says "no longer owed-Andy's-local-hands" + `layer0-apply` |
| Operating model (carry) | `aidstation-sources/CARRY_FORWARD.md` | first section = **Ops automation / operating model — LIVE (2026-06-15; record issue #630)** |
| State pointer | `aidstation-sources/CURRENT_STATE.md` | top entry: `primary_movement` DONE/applied + ops automation + `layer0-validate-live` PASS + #630 + this handoff named |
| Apply workflow | `.github/workflows/layer0-apply.yml` | `environment: production` |
| Redump workflow | `.github/workflows/layer0-redump.yml` | `pg_dump --schema=layer0` |
| Diag query workflow | `.github/workflows/neon-query.yml` | `NEON_RO_DATABASE_URL` + `default_transaction_read_only=on` |
| Validate-live workflow | `.github/workflows/layer0-validate-live.yml` | `cron: "0 7 * * *"`; verified live run = PASS |
| CODEOWNERS | `.github/CODEOWNERS` | `/etl/migrations/ @ahorn885` (soft) |
| Prod state | live Neon (via `neon-query`) | 24 active disciplines, 0 NULL `primary_movement`, `0A-v1.6.8` |
| Issues | #616, #630 | both closed completed |
| Owed | — | nothing on these arcs; T3-refresh re-verify carried |
