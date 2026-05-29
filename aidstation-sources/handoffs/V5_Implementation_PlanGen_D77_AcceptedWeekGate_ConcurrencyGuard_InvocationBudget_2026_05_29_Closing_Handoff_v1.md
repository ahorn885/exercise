# V5 Implementation — D-77 Plan-Gen: Accepted-Week Gate + Concurrency Guard + Per-Invocation Budget — Closing Handoff

**Session:** Implementation. Live triage of a fresh PGE re-run (`plan_version_id=36`), then three structural fixes that move D-77 from "converges but every week is rejected" to "should produce accepted weeks and stop the cost/504 loop." Merged as **PR #311** (merge commit `7f203f28`).
**Date:** 2026-05-29
**Predecessor handoff:** `V5_Housekeeping_DocsToGitHubIssues_NextStepsFramework_2026_05_28_Closing_Handoff_v1.md`
**Branch:** `claude/relaxed-goodall-PaeOm` (PR #311, merged to `main`)
**Status:** 3 substantive commits (1 new module, 2 new/edited test files, 2 edited app files) + this handoff. Suite **1811 passed / 16 skipped**. **No migration.**

---

## 1. TL;DR

The cache-key money-loop (PR #294, `last_sync` day-anchor) is **confirmed dead** from the `pv=36` prod logs: `llm_layer3a_athlete_state … HIT` every pass, blocks cache and replay as HIT. What remained was **two distinct problems the prior chain had folded together as "latency"**:

1. **No week could ever be ACCEPTED** (the real go-live gate). `volume_band` graded Mon–Sun ISO-week slices against full-week bands, but blocks are anchored to the (non-Monday) phase start — so every compliant week split across two ISO buckets and false-failed `volume_band_below(blocker)`. Every `pv=36` block was `accepted=False` best-effort. **A plan of best-effort weeks never validates clean → never the proof of go-live.**
2. **The 504-loop was cost + throughput, not convergence.** ~5 overlapping invocations (every-minute cron × 300s functions + poller) duplicate-synthesized the same frontier week; and each invocation greedily started a 2nd block it couldn't finish, 504-killing a billed Anthropic call every pass.

All three fixed; details + the one owed re-run below.

---

## 2. The decisive evidence (from `pv=36`, prod deploy `dpl_2Pp3…` = commit `f14421a`)

The full un-truncated `synthesize_phase` line Andy pasted (the Vercel MCP log viewer truncates to ~30 chars/line — **see §6 gotcha**):

```
23:06:10.540 block idx=3 Build:w4 MISS — synthesizing
23:08:40.968 HTTP POST api.anthropic.com 200 OK
23:08:41.004 Build:w4 attempt 1/3 llm call 148934ms (in=7843 out=9543 max_tokens=9200)
23:08:41.005 Build:w4 attempt 1 validator rejected (25 failure(s)): volume_band_below_week_25_D-009_build(blocker); volume_band_below_week_25_D-008_build(blocker); … week_26 …
23:08:41.005 Build:w4 per-block budget spent (148934ms over 1 call(s)) — accepting best-effort attempt (cap_hit)
23:08:41.005 Build:w4 done — 1 llm call(s), 148934ms total, accepted=False, cap_hit=True, retries_used=0, sessions=13
23:09:15.472 block idx=4 Peak:w1 MISS — synthesizing      ← starts a 2nd block
23:10:30.452 Vercel Runtime Timeout Error: Task timed out after 300 seconds   ← killed mid-call
```

What it proves, numerically (no longer inference): one week-block = **one** 149s Anthropic call returning **200 OK** with `sessions=13` (so NOT a freeze/missing-data hang); rejected only by `volume_band` (`schema_violation`=0, `clamping`=0); a **single 1-week block emits TWO ISO-weeks of failures** (`week_25`+`week_26`) — the bucketing tell; and the function starts a 2nd block at 23:09:15 then 504s at 23:10:30 — the wasted-call tell. `out=9543` with `sessions=13` (~600 tok/session ≈ 7.8k) ⇒ **writing-bound, not thinking-bound** — trimming the thinking budget would NOT have helped (overturns the prior chain's lead fix).

---

## 3. What shipped (PR #311, 2 commits)

### Commit 1 — `3db3957` volume_band: bucket by training week, not ISO week  *(the accepted-week gate)*
- `layer4/validator.py` `_rule_volume_band`: bucket key `_iso_week(s.date)` → `s.phase_metadata.week_in_phase`. The band comparison is **unchanged** — a genuinely under-volumed week still fails; we only stop splitting one training week into two half-week buckets. `rule_name`/`detail` now report `week_in_phase` (matches the synthesizer's mental model). `_iso_week` is retained (still used by the frequency rule, `validator.py` ~L766/L876 — same latent class but it under-counts → false-PASS, not a blocker; flagged, not fixed).
- **Why the suite missed it:** every `test_layer4_validator.py` fixture uses `_SCOPE_START = date(2026, 6, 1)` — a **Monday** — so training-week == ISO-week and the straddle never occurred. `pv=36` started **Wed 2026-04-01**.
- **Local repro that proved it** (real validator, identical compliant 6h week): Monday start → 0 failures; Wednesday start → `volume_band_below_week_15 [blocker]: actual 1.0h vs band (5.0-8.0h)`.
- Tests (+2): `test_volume_band_non_monday_compliant_week_no_false_blocker` (red before the fix), `test_volume_band_non_monday_genuine_undershoot_still_blocks` (guards against masking a real undershoot; fires once per training week, not once per ISO week).

### Commit 2 — `1258702` concurrency guard + per-invocation budget  *(cost/504)*
- **Concurrency guard** (`routes/plan_create.py`): `_try_acquire_advance_lock` runs `pg_try_advisory_lock(_ADVANCE_LOCK_NS, plan_version_id)` at the top of `_advance_plan_generation` (after the terminal short-circuits, before the cone). One invocation advances a plan; the rest return `{"status":"generating","note":"advance_in_progress_elsewhere"}`. **Session** lock → auto-releases when the connection closes (request teardown OR a 504 dropping the conn), so a killed pass never strands it. Fails **open** on a null/non-`locked` row (the non-Postgres FakeDb in unit tests), so the guard is inert in tests unless contention is simulated.
- **Per-invocation budget** (new `layer4/generation_budget.py`): a `ContextVar` monotonic deadline (no cache-key/plumbing impact). `generation_deadline(budget_s)` ctx-manager set by the route around `orchestrate_plan_create`; `generation_deadline_passed()` checked in the engine's `_serialize_block` closure (`layer4/plan_create.py`). It gates **only a cache MISS** (HIT replay is never gated) and **never the first synthesis of a pass** (`synth_count[0] >= 1` guard) — so every pass makes **≥1 block of progress** while never starting a block it can't finish. Stop signal `Layer4GenerationIncomplete` is a **`BaseException`** (NOT `Exception`) so the broad `except Exception` handlers in the cached-wrapper/orchestrator/route synthesis path can't swallow it; the route's explicit `except Layer4GenerationIncomplete` keeps the row `generating` (next pass resumes from cache) → `{"status":"generating","note":"budget_partial_progress"}`.
- **Budget is env-sized off the Vercel function cap:** `_FUNCTION_CAP_S = PLAN_GEN_FUNCTION_CAP_S` (default 300), `_INVOCATION_RESERVE_S = PLAN_GEN_INVOCATION_RESERVE_S` (default 255), `_INVOCATION_BUDGET_S = max(cap - reserve, 30)`. **The whole point:** raise the dashboard Max Duration to 800s + set `PLAN_GEN_FUNCTION_CAP_S=800` → ~545s usable → ~3–4 blocks/pass, no code change.
- Tests: new `tests/test_plan_create_concurrency.py` (lock contract incl. fail-open; skip-when-held; deadline expiry/reset; `BaseException`-not-swallowed; budget-incomplete keeps row generating). 3 existing `TestStallBackstop` tests updated to queue the extra lock-response row.
- Functional proof of the gate contract (4 cases, all pass): deadline-passed → block0 still synthesizes, stops at block1; ample budget → all synthesize; no deadline → nothing gated; instantly-blown budget → still ≥1 block of progress.

---

## 4. ⚠ Owed (Andy's hands) — the go-live proof

DB egress to Neon + Vercel deploy are both blocked from the container, so this is yours:

1. **(Recommended) Raise Vercel Function Max Duration → 800s** (dashboard; Pro allows it) and set env **`PLAN_GEN_FUNCTION_CAP_S=800`**. Skip the RAM bump (pv=36 used ~340MB/2048 ≈ 17%); CPU 1→2 is optional/marginal (the 149s is the Anthropic call, not CPU).
2. **Redeploy `main`** (now at merge `7f203f28`) + **create ONE fresh PGE 2026 plan.**
3. **Read the log for the proof:**
   - `synthesize_phase: <phase>:w<n> done — … accepted=True` ← **the first accepted week (THE go-live milestone).** `volume_band` failures should be gone.
   - One advancer per minute — no 5× duplicate `MISS` on the same block (concurrency guard).
   - Each pass cleanly banks a few blocks and returns (no `Vercel Runtime Timeout`); plan reaches `generation_status='ready'`.
   - Then the **§14 coherence read**: open the rendered plan, read across week boundaries within a phase — do the independently-generated weeks blend (gentle ramp, planned recovery) or show cliffs? That's the Slice-3 stitcher decision (#203).
4. **If a few real `volume_band_below` survive** after the fix → that's a *genuine* undershoot, now cleanly isolated from the bucketing artifact → a modeling decision (Tier-2-B / #293), not a convergence blocker.

---

## 5. Still open (NOT addressed this session)

- **(B)** Genuine `volume_band` undershoot, if any survives §4.4 — modeling decision (#293 / Tier-2-B).
- **(C)** ~150s/block latency is writing-bound (`out`≈9.5k, `sessions=13`); the lever is fewer sessions/block or smaller blocks (`_BLOCK_WEEKS`), NOT thinking budget. Only matters if a single block ever approaches the (raised) cap.
- **(D)** `unknown discipline_category 'Navigation'(D-015)/'Cycling'(D-008)` → defaulting to 'Mixed'; `sport_locale_incompatible_D-008_home` — Layer 0 data hygiene (Tier-2-D).
- **Frequency rule** (`validator.py` ~L766/L876) buckets by `_iso_week` too — same class, but false-PASS not false-fail, so non-blocking. Cheap follow-on to align with `week_in_phase`.
- Slice-3 week-seam stitcher (#203) — only meaningful once convergence + acceptance hold.

---

## 6. Operating notes (re-investigation killers)

- **Vercel runtime-log viewer truncates each line to ~30 chars** (one representative row per request). It is a reliable **boolean oracle** (a content query matches/doesn't — verified with a nonsense-string control returning 0) but **cannot show numbers** (latency/tokens/sessions). To read actual values, open the Vercel dashboard log (or `vercel logs <deployment-url>`) — not truncated there. The numeric lines that matter: `synthesize_phase: <p>:w<n> attempt 1/3 llm call <N>ms (in= out= max_tokens=)` and `… done — … accepted= cap_hit= sessions=`.
- **Env was flaky this session:** parallel tool-call batches were intermittently cancelled (only the first ran) and `grep -c`/display occasionally corrupted. Mitigation that worked: **one operation per call**, write results to a `/tmp` file and read it back, and cross-verify critical state via multiple channels (Python file-read + GitHub API). All final state was confirmed clean.
- **Test baseline:** 1811 passed / 16 skipped (the 16 need `ANTHROPIC_API_KEY`). Container has no venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then `/tmp/venv/bin/pytest tests/`.
- **DB is Postgres-only** (`database.py` → psycopg2, requires `DATABASE_URL`); the route/cron unit tests use an in-file `_FakeConn` with a FIFO `queue_response` — any new DB call added to `_advance_plan_generation` must be matched by a queued response in those tests (that's why the 3 stall tests needed the extra lock row).

---

## 7. Session-end verification (Rule #10)

| Check | Result |
| --- | --- |
| volume_band buckets by `week_in_phase` (not `_iso_week`) | ✅ `layer4/validator.py` |
| Repro: compliant Wed-start week → 0 failures post-fix | ✅ local real-validator run |
| Concurrency guard acquires per-plan advisory lock before the cone | ✅ `_try_acquire_advance_lock` |
| Budget never gates the first block of a pass (≥1 progress/pass) | ✅ 4-case functional proof |
| `Layer4GenerationIncomplete` is BaseException (not swallowed) | ✅ test + `issubclass` assert |
| Budget env-sized off `PLAN_GEN_FUNCTION_CAP_S` | ✅ `routes/plan_create.py` |
| No migration / no prompt change | ✅ |
| Full suite | ✅ 1811 passed / 16 skipped |
| PR #311 merged to `main` | ✅ merge `7f203f28` |

---

**End of handoff.**
