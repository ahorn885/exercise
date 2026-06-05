# V5 Implementation — Layer 4 strength exercise-surface (#335) + plan-gen diag observability (pv=57 stall root-cause)

**Date:** 2026-06-05
**Branch:** `claude/v5-layer4-handoff-9q4Vs`
**PR:** #421 (this session — strength surface #335 Slices 1&2 + `movement_patterns`/core-accessory + diag observability + stall snapshot + date-fixture fix). **CI green; merged to `main`.**
**Issues:** #335 (strength = bare labels) — Slices 1&2 shipped; #316 (latency) — re-scoped by the real root cause; #418 (observations have no reader) — untouched.

---

## ⚡ Diagnostic token (read this first — used every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```

Read any plan's state past the login wall:
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc`

- WebFetch gets a **403** (Vercel deployment protection) — fetch via the **Vercel MCP `web_fetch_vercel_url`** tool, which authenticates. (`mcp__…__web_fetch_vercel_url`.)
- The diag JSON now (this session) carries: `generation_status`, `generation_error`, `generation_traceback`, `blocks_snapshotted`, `generation_units_cached`, `total_sessions`, **`advance_lock_until`**, **`server_now`**, **`block_timing`** (total/max `latency_ms`, total_retries, any_cap_hit, last_snapshot_at), and **`blocks[]`** (per-block phase_idx/phase_name/session_count/`synthesis_metadata`/snapshot_at).
- Runtime-log MCP **truncates the message column** + full-text search gives unreliable negatives. For a full untruncated log line (e.g. `llm_layer3a … HIT/MISS ibundle=…`, `synthesize_phase …`), pull it from the **Vercel dashboard** (Rule #14) or filter by `requestId`. Vercel team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`.

---

## 1. What this session was

Andy ran a fresh cold PGE plan (**pv=57**) to exercise the seam fix (#416). It **stalled at block 3 / ~6** (`Peak:w1`). Pulling the *actual* logs (per Rule #14 — Andy's standing instruction "always pull the logs, never assume errors") root-caused it precisely, after I twice mis-theorized from truncated table data (a "300s gateway" that was actually the **800s `FUNCTION_INVOCATION_TIMEOUT`**, and a "lock leak / clean-release-ineffective" story the detailed log disproved).

**Root cause:** the per-phase synthesizer prompt rendered only `effective_pool size=N` (a count), **never the resolved exercise list**. So the model invented strength `exercise_id`s (`goblet_squat`, `EX-L001`, …) → validator Rule 6a rejected every one as `equipment_unavailable` (even for gear Andy owns; the id was never in the resolved set). That under-specified task also drove a **395s thinking attempt that hit `max_tokens` with empty output** on `Peak:w1`, cascading to the 800s timeout that stalled the plan. **This is #335** (strength surface), and it was upstream of both the equipment blockers *and* the latency/stall. Andy's instinct — "if the calls were efficient they'd succeed in the window" — was correct.

**Fixed + shipped (PR #421, merged):** the strength exercise surface (the go-live fix) + the diag tooling that let me debug it + the stale test-date that was failing the suite.

---

## 2. Shipped (PR #421 — 6 commits, all green; NO migration)

### Go-live fix — #335 strength programming
- **Slice 1 — exercise-surface rendering + prompt** (`layer4/per_phase.py`): `_format_strength_exercise_pool()` renders `=== Strength exercise pool ===` (per locale, per included discipline in 2A load-weight order; ranked Critical→High→Medium then preferred movement-pattern then Tier-1; 2D-excluded dropped; deduped; capped at `_STRENGTH_POOL_CAP_PER_DISCIPLINE=10`). `SYSTEM_PROMPT` `# Strength programming` section (verbatim from the signed-off design §9): pick from the rendered pool, **never invent `exercise_id`s**; per-phase dose; RM/RPE loads; unilateral/offset bias; attribution + scheduling + honor 2D.
- **`movement_patterns` threaded** (`layer2c/builder.py` + `layer4/context.py`): `layer0.exercises.movement_patterns` existed and 2D already read it; the 2C query was one column short. Added `e.movement_patterns` → `ResolvedExercise.movement_patterns` (defaulted `[]` so pre-change cached 2C payloads hydrate). Powers the pattern ranking + the **data-driven core/accessory split** (Andy's call): core = priority Critical/High **and** a compound pattern (Hinge/Squat/Lunge/Single-Leg), capped 3/discipline; priority *is* the sport-relevance ranking.
- **Slice 2 — `strength_frequency_band` validator** (`layer4/validator.py`): advisory (`warning`, never blocks — Phase 1 lesson). Per (phase, week_in_phase), strength-session count vs `_STRENGTH_SESSIONS_PER_WEEK` (Base/Build 2, Peak/Taper 1) ±1. Catches the bare/empty-strength regression. Appended to `_ALL_RULES`.

### Diag observability (debugging surface)
- **Per-block timing + lock state in the diag JSON** (`routes/admin.py`): pure `_summarize_progress_blocks()` + `advance_lock_until`/`server_now` (see token callout above). The persisted `synthesis_metadata` was already on the HTML inspect page but dropped from the token-readable JSON.
- **Stall reaper self-explains** (`routes/plan_create.py`): `_stall_diagnostic_text()` writes the gate's measured anchor/age/window/cached-count into `generation_traceback` (was NULL on a stall, since a stall is a wall-clock gate not an exception).

### Test hygiene
- **`tests/test_layer4_plan_create.py` `_PLAN_START` → `date.today()`** (was hardcoded `date(2026,6,1)`): 45 failures were purely calendar staleness (the `plan_start_date_in_past` guard). Verified weekday-agnostic (suite green on a Friday start — weeks bucket by `week_in_phase` offset, not calendar week). The **product form already** defaults to today + sets `min=today` + the route rejects past dates server-side — this was only the fixtures.

---

## 3. The pv=57 diagnosis (for the record — the corrections matter)

- **The kill is the 800s Vercel function timeout** (`FUNCTION_INVOCATION_TIMEOUT`, request `bd6z7-…`, `Duration: 800047ms`), **not a ~300s gateway.** The CLAUDE.md "Function Max Duration = 800s" is right; the handoff-§4 "~300s gateway" framing was wrong.
- **The cone is a clean HIT** on reclaim (`llm_layer3a … HIT ibundle=b6069931`, stable across passes) — *not* re-computing. Cone-determinism is NOT the issue.
- **Block timings (Source B):** Build w1/w2/w3 = 242/164/182s, all `cap_hit=True` (exceed the 120s per-block soft budget), `accepted=False` with `equipment_unavailable` blockers swept under `cap_hit`. `Peak:w1` thinking attempt = **395s, 26600/26600 tokens, empty tool args, stop_reason=max_tokens**; the forced-tool retry then succeeded in **99s** — proof the block is synthesizable fast once the task is well-specified.

---

## 4. Carry-forward (deferred; details in `CARRY_FORWARD.md`)

- **#335 Slice 3 (deferred):** §3 **3A-strength-state dose modulation** — the *base* dose (2/2/1/1) ships; personalizing it by the athlete's 3A strength state (low → hold 2× longer; high → maintenance sooner) is not wired (needs the 3A strength-state field). Plus Phase 2b `rx_engine` absolute loads (#335).
- **Layer 2B cache-key drift:** at 12:35 only `l2b` drifted (`f17c69d0`→`5fcf7380`) while all other cone hashes held → re-keys blocks → re-synth churn. The #199/#294 determinism class, now on 2B. Worth a determinism fix.
- **Advance-lock TTL (310s) < real max function duration (800s):** a long pass outlives its own lock → a concurrent pass can reclaim mid-flight. Align the TTL to the real ceiling (or cap pass wall-clock < TTL).
- **`PLAN_GEN_FUNCTION_CAP_S` env tune (Andy's call):** currently **300** (budget 30s → 1 block/pass). With the strength fix removing the thrash and the real ceiling confirmed at **800s**, raising it back toward **800** (budget ~470s → ~2 blocks/pass) would be *faster* and is safe — the earlier "don't raise it" caution was under the now-disproven 300s-gateway hypothesis. **Not required** for the run to succeed (cap=300 works, just 1 block/pass). Reversible.
- **#316 latency:** re-scoped — the structural latency limiter is now understood as per-block synthesis cost (164–242s, cap_hit) under the 800s ceiling, gated to 1 block/pass by the budget.

---

## 5. Issues

- **#335** — strength = bare labels. **Slices 1&2 shipped** (PR #421). Slice 3 (3A modulation) + Phase 2b (rx_engine) remain.
- **#316** — latency. Re-scoped (above); not a blocker for the next run.
- **#418** — Layer 4 observations have no reader. Untouched.

---

## 6. Owed + next moves

### 6.1 Owed deploys
- **NONE owed beyond the merge.** This session added **no DB migration** (`movement_patterns` is read from an existing 0B column; diag/stall reused existing `advance_lock_until`/`generation_traceback`; the rest is code/prompt). Merging PR #421 → `main` redeploys prod via the git-main alias.
- **Expected on the first post-merge cold plan:** a one-time **cold cone + cold blocks** (the prompt + 2C-payload changes shift the per-phase content-addressed cache key — expected, not a regression).

### 6.2 Next move — the cold-plan re-run (Andy, new session)
Kick a fresh cold PGE plan and monitor via the **diag token** (callout at top). **Win conditions:**
1. **No `equipment_unavailable` blockers** — the model now prescribes real resolved `exercise_id`s (check `blocks[].synthesis_metadata` / runtime `validator rejected` lines).
2. **No 395s runaway** — blocks synthesize in ~100–250s (`block_timing.max_block_latency_ms`); `cap_hit` may still be true on dense weeks but the block completes.
3. **`blocks_snapshotted` climbs to `ready`** — finally exercising the seam fix (#416). Watch `advance_lock_until` + `server_now` for the clean per-pass cadence.
If it stalls again, `generation_traceback` now carries the **stall diagnostic** (anchor/age/window) and `block_timing` localizes the slow block — read both from diag directly.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (note the no-migration + the env-tune item)
4. This handoff (the diagnostic token is in the ⚡ callout at the top)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 7. Test / verification state

- Full suite (in-container, 2026-06-05): **green** — the 45 prior failures were all the `test_layer4_plan_create.py` date-staleness, now fixed (`_PLAN_START = date.today()`). New tests: `tests/test_layer4_strength_pool.py` (pool rendering/ranking/core-accessory), `tests/test_layer4_strength_frequency.py` (the band validator), `tests/test_routes_admin.py::TestSummarizeProgressBlocks`, `tests/test_plan_create_concurrency.py` stall-diagnostic.
- No live-DB / LLM run from the container (Neon egress blocked) — the cold-plan re-run (§6.2) is the real proof.

---

## 8. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Strength pool rendered | `layer4/per_phase.py` | `grep -n "_format_strength_exercise_pool\|=== Strength exercise pool ===" layer4/per_phase.py` |
| Prompt: pick from pool, never invent | `layer4/per_phase.py` | `grep -n "# Strength programming\|never invent .exercise_id" layer4/per_phase.py` |
| `movement_patterns` on the payload | `layer4/context.py` | `grep -n "movement_patterns: list\[str\]" layer4/context.py` |
| 2C query selects it | `layer2c/builder.py` | `grep -n "e.movement_patterns" layer2c/builder.py` |
| Strength frequency validator | `layer4/validator.py` | `grep -n "_rule_strength_frequency_band\|_STRENGTH_SESSIONS_PER_WEEK" layer4/validator.py` (in `_ALL_RULES`) |
| Diag block timing + lock | `routes/admin.py` | `grep -n "_summarize_progress_blocks\|advance_lock_until\|server_now" routes/admin.py` |
| Stall self-explains | `routes/plan_create.py` | `grep -n "_stall_diagnostic_text" routes/plan_create.py` (passed as `traceback_text` in the stall branch) |
| Test date no longer hardcoded | `tests/test_layer4_plan_create.py` | `grep -n "_PLAN_START = date.today()" tests/test_layer4_plan_create.py` |
| Design status (Slices 1&2 done) | `aidstation-sources/Layer4_StrengthProgramming_Phase2_Design_v1.md` | `grep -n "Slices 1 & 2 implemented" Layer4_StrengthProgramming_Phase2_Design_v1.md` |

---

*End of handoff.*
