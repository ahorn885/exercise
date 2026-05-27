# Plan-Gen D-77 — Layer 2E cache-key determinism + stall-backstop orphan-scoping (the convergence loop's real root cause) — Closing Handoff

**Session:** Live-incident close, log-driven. Andy redeployed the block-`max_tokens` fix (PR #197) and re-ran the PGE plan — it still failed. This session finally read the **prod Vercel logs** (the prior three sessions diagnosed code-only, no log in hand) and pinned the actual non-convergence root cause: a **second instance of the c4f9160 cache-key non-determinism bug** that fix missed — `Layer2EPayload.computed_at`. Shipped that fix (PR #199, merged), then the re-run exposed a **new** immediate-failure mode — the stall backstop false-tripping on the prior failed plan's orphaned cache rows — and shipped that fix too (PR #200).
**Date:** 2026-05-27
**Predecessor handoff:** `V5_Implementation_PlanGen_D77_BlockMaxTokens_SchemaViolationFix_2026_05_27_Closing_Handoff_v1.md`
**Branch:** `claude/review-run-logs-A4JVs`
**PRs:** **#199** (Layer 2E `computed_at` day-anchor + convergence diagnostics) — **MERGED** `9012430`. **#200** (stall-backstop orphan-scoping) — opened this session.
**Status:** 2 substantive code files + 2 test files across the two PRs + `Layer4_Spec §11.5` + bookkeeping. Suite **1796 passed / 16 skipped**. **No migration** (both fixes are query/sampling-level; existing orphan cache rows simply stop mattering).

---

## 1. The finding (why every prior fix's re-run still failed — and then failed differently)

**Read the actual prod logs this time.** The prior three sessions all diagnosed code-only ("the prod log was NOT in hand"). This session pulled the Vercel runtime logs for the two failed `plan_version_id=29` runs and for the four `plan_version_id=30..33` runs that followed PR #199's deploy. Two distinct bugs, in sequence:

**Bug A — Layer 2E `computed_at` poisons every Layer 4 block cache key (the convergence root cause; PR #199).** The `pv=29` runs 504-looped: `max_tokens=9200` was live (PR #197 deployed), `schema_violation` was GONE (PR #197 worked), but every cron/poller pass 504'd with an Anthropic call in flight, `accepted=True` never appeared, and no block ever converged. Root cause traced via a cache-determinism audit: `Layer2EPayload.computed_at` (`layer2e/builder.py:1156`) was stamped `datetime.now(timezone.utc)` at **full microsecond precision**. The cone is **rebuilt on every resumable pass** (the c4f9160 finding), and `computed_at` is a non-excluded field that hashes into `layer2e_hash` → `plan_create_key` (the `call_cache_key`) → **every** `compute_block_cache_key`. So each pass minted *different* block keys → every block synthesized the previous pass was orphaned → the synthesizer re-ran from block 0 every pass → exceeded the 300s cap → 504, re-paying the full extended-thinking synthesis each minute (**this is the ~$50 burn**). It is the **exact same bug class** c4f9160 day-anchored for `layer1.as_of` and `layer2a.generated_at` — that fix simply **missed Layer 2E** (2E runs *after* 3B, so its hash poisons Layer 4 keys but not 3A/3B keys, which is why 3A/3B cached fine and only Layer 4 looped). It also silently defeated the stall backstop: orphan rows kept `_count_cached_blocks` climbing, so the no-progress gate never tripped.

**Bug B — stall backstop false-trips on the prior plan's orphan rows (the new immediate-failure; PR #200).** After PR #199 deployed, Andy created plans `pv=30,31,32,33` in quick succession; **each failed immediately** (`POST /generate` → 200 fast, message `_advance_plan_generation: D-77 stall backstop tripped`). A brand-new plan can't be 900s old, so this was a false-trip. Root cause: `_generation_stalled` measured `NOW() - MAX(block.created_at)` scoped to the **user**, not the current plan. The orphaned block rows `pv=29` wrote (~08:13, over an hour earlier) anchored the elapsed-time window in the past, so `NOW() - <old orphan time> > _STALL_WALLCLOCK_S=900` on every new plan's first pass. PR #199 stopped *new* orphans but couldn't un-poison the existing ones, and the user-scoped query had no plan boundary. **This bites any user with a prior failed plan** — it gets worse with more users, not better.

## 2. What shipped

**PR #199 — `layer2e/builder.py` (day-anchor) + diagnostics.**
- `computed_at=datetime(today.year, today.month, today.day, tzinfo=timezone.utc)` — day-anchored to the cone's logical `today` (already normalized non-None at `builder.py:1081`). Deterministic, day-granular, no wall-clock dependency, unit-testable with a fixed `today`.
- **`layer4/cached_wrappers.py`** — one `print` per pass logging `call_cache_key={key[:12]} [l1=… l2a=… … l2e=… l3a=… l3b=…]`. If the key drifts between two passes of the same plan, the per-layer prefixes name the guilty layer in one read (this is the line that would have caught Bug A instantly).
- **`layer4/cache.py`** — `get_phase_or_synthesize` logs per-block cache **HIT** vs **MISS** (`block idx=… <phase>:w<n> HIT/MISS key=…`), so convergence progress (reuse) vs key-churn (orphaning) is visible at a glance.
- Test: `tests/test_layer2e.py::TestPGEBaseline::test_computed_at_day_anchored_for_stable_cache_keys`.

**PR #200 — `routes/plan_create.py` (orphan-scoping).**
- `_generation_stalled`: the block subquery is bounded `AND created_at >= pv.created_at` (correlated to the outer `plan_versions pv`). Orphans created before this plan started no longer anchor the window. Param list unchanged (the bound is SQL-side).
- `_count_cached_blocks(db, user_id, plan_version_id)`: same `created_at >= pv.created_at` bound (now joins `plan_versions pv`), so the progress count/telemetry isn't inflated by prior-plan orphans either. Caller at `_advance_plan_generation` updated.
- Tests: `TestCountCachedBlocks` + `TestGenerationStalled` updated to assert the `created_at >= pv.created_at` bound (the pv=29 → pv=30+ regression guard).

**Scope decision — did NOT touch the `max_tokens`/block-size knob.** With Bug A fixed, the resumable model works again: a 504'd pass now caches its completed blocks and the next pass *reuses* them → monotonic progress. So the 504s become survivable. Whether a *single* dense-week call still exceeds 300s (→ even one block never caches) is data-gated and now measurable from the new diagnostics — left for Andy's decision (Trigger #5; coherence-vs-latency tradeoff).

## 3. Code / tests

Full suite **1796 passed / 16 skipped** (`/tmp/venv`). `pyflakes` clean on all four changed code files (the two pre-existing unused-import findings in `tests/test_routes_plan_create.py` lines 18/35 predate this session — not introduced here, not touched).

## 4. Owed actions + manual verification

- **⚠ Owed (Andy's hands), in order:**
  1. **Merge PR #200 + redeploy.** (PR #199 already merged + deployed as prod `dpl_3TBk4on2…` / `9012430`.) No migration — both fixes are query/sampling-level; the existing `pv=29` orphan rows simply stop mattering, so nothing to clear.
  2. **Create one fresh plan** (the PGE case). It should now get *past the gate* (the cone runs) instead of failing instantly — that alone proves Bug B fixed.
  3. **Confirm convergence from the new logs** — this is finally the real test of the whole D-77 arc:
     - `llm_layer4_plan_create_cached: … call_cache_key=<X> [l1=… l2e=… …]` should show the **SAME `call_cache_key` across passes** of the same plan (it was drifting before). If it still drifts, the per-layer prefixes name which hash moved.
     - `layer4 cache: block idx=… <phase>:w<n> HIT key=…` should fire on later passes (reuse → monotonic progress). MISS-on-every-pass = key churn (shouldn't happen now).
     - `synthesize_phase: <phase>:w<n> done — … accepted=True …` should fire per block, and the plan should reach `ready`.
  4. **Watch the per-attempt latency line** `synthesize_phase: … llm call <N>ms (… max_tokens=9200)`. If a single dense-week call approaches 300s, that's the remaining (separate) decision — see §5.

## 5. Next session — deferred follow-on(s)

1. **Single-call latency (only if a re-run still 504s without ever caching one block).** Now that caching works, the only residual 504 risk is one block's first call exceeding 300s. If the latency line shows that, the fix is to shrink the unit (`_BLOCK_WEEKS` / sessions-per-block) or trim `extended_thinking_budget` for blocks — a coherence-vs-latency tradeoff (Trigger #5). **Data-gated — don't pre-tune.**
2. **Coherence (design §14, still UNVERIFIED).** Once a plan reaches `ready`, read across week boundaries WITHIN a phase — do the independently-generated weeks blend (gentle ramp, planned recovery) or show cliffs/duplication? If not, the seam may be wrong (a design redo, not a tuning knob) — report before Slice 3.
3. **Slice 3** (intra-phase week-seam stitcher; own Trigger #1 prompt pass) remains after convergence + coherence are confirmed.
4. **Cleanup (optional):** the two pre-existing unused imports in `tests/test_routes_plan_create.py` (`pytest` L18, `Layer3BOutputError` L35).

## 6. Operating notes for next session (read order, Rule #13)

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what shipped (these two fixes) + the owed merge/redeploy/re-run.
3. `aidstation-sources/CARRY_FORWARD.md` — the D-77 entry (root cause now ✅ found + fixed).
4. `aidstation-sources/Layer4_Spec.md §11.5` — the cache-key-determinism + stall-scoping fix records.
5. This handoff + the block-`max_tokens` predecessor.
6. `./aidstation-sources/scripts/verify-handoff.sh` — anchor sweep.

## 7. Session-end verification (Rule #10)

| Check | Result | Anchor / method |
|---|---|---|
| Layer 2E `computed_at` day-anchored | ✅ | `layer2e/builder.py` — `computed_at=datetime(today.year, today.month, today.day, tzinfo=timezone.utc)` |
| Per-pass cache-key diagnostic | ✅ | `layer4/cached_wrappers.py` — `print(f"llm_layer4_plan_create_cached: … call_cache_key={key[:12]} [l1=… l2e=… …]")` |
| Per-block HIT/MISS diagnostic | ✅ | `layer4/cache.py` — `get_phase_or_synthesize` prints `block idx=… HIT/MISS key=…` |
| Layer 2E determinism test | ✅ | `tests/test_layer2e.py::TestPGEBaseline::test_computed_at_day_anchored_for_stable_cache_keys` |
| Stall backstop plan-scoped | ✅ | `routes/plan_create.py` — `_generation_stalled` + `_count_cached_blocks` bound `created_at >= pv.created_at` |
| Stall-scoping tests | ✅ | `tests/test_routes_plan_create.py` — `TestGenerationStalled` / `TestCountCachedBlocks` assert the bound |
| Full suite | ✅ | 1796 passed / 16 skipped (`/tmp/venv`) |
| CURRENT_STATE pointer flipped | ✅ | → this file; block-`max_tokens` fix demoted to predecessor |

## 8. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Fix `layer2e.computed_at` by day-anchoring to `today` (vs. day-anchoring `now()`) | Claude | `today` is already threaded + normalized; deterministic regardless of build wall-clock; unit-testable without a clock dependency; ties provenance to the cone's logical day. |
| **D2** | Bound `_generation_stalled` + `_count_cached_blocks` to `created_at >= pv.created_at` (vs. clearing orphan rows, or keying to call_cache_key) | Claude | No migration, no manual cleanup, no DB access needed (Neon blocked from the container). The route doesn't hold the orchestrator-derived `call_cache_key`; the `created_at` bound is the per-plan correctness fix that works for all users. |
| **D3** | Do NOT change the `max_tokens`/block-size knob this session | Claude | With Bug A fixed, resumability makes 504s survivable. Whether a single call exceeds 300s is now measurable from the new logs; pre-tuning a coherence-vs-latency tradeoff blind is the wrong move (Trigger #5). |

## 9. Files shipped this session

**Substantive (2 code + 2 test, across PR #199 + #200):** `layer2e/builder.py`, `layer4/cached_wrappers.py`, `layer4/cache.py`, `routes/plan_create.py`; `tests/test_layer2e.py`, `tests/test_routes_plan_create.py`. Plus `aidstation-sources/Layer4_Spec.md` (§11.5).
**Bookkeeping:** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, `Project_Backlog_v62.md` (changelog + D-77 row), this handoff.

**End of handoff.**
