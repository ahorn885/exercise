# V5 Implementation — Plan-Gen pv=40 Verification + Per-Block `max_tokens` Truncation Fix — Closing Handoff (2026-05-30)

**Session:** Watched the live #325 verification run (pv=40), caught it **fail**, root-caused the failure end-to-end from the runtime logs, and shipped the truncation fix (**PR #327, merged**). One PR merged (#327); no issues filed (the fix closes the proximate pv=40 blocker; the deferred items below are already-known #316/#324 territory).

**All app code is on `main` and deployed-on-cold-start.** No migration. The single owed action is the **re-verification run** (Andy's hands).

---

## 1. What happened — pv=40 verification FAILED, then fixed

The prior handoff's headline next action was *"verify #325 — generate one PGE plan and confirm it reaches `ready`."* Andy kicked off pv=40 on the post-#325/#326 deploy (`e8f59a8`). I watched it live via the Vercel runtime logs.

**It failed — but NOT like pv=39.** pv=39 made 7 good blocks then lost them; **pv=40 cached ZERO blocks** and tripped the 900s stall backstop at ~15.5 min (`_advance_plan_generation: D-77 stall backstop tripped`, `routes/plan_create.py:392`), surfacing the generic *"Plan generation stalled… contact support."* The admin inspect (`/admin/plan/40/inspect`) confirmed **0 cached / 0 snapshotted / 0 sessions**.

### The root cause (pinned from the prod log `detail` line)

The failing `detail`, identical across all ~15 passes (deterministic):

> `model did not emit a record_phase_sessions tool_use block (stop_reason=max_tokens)`

The first week-block's synthesis **truncated against its output ceiling** before the model emitted the `record_phase_sessions` tool call → `Layer4OutputError(schema_violation)` → #325 treated it as a retryable block-fumble → retried the *same deterministic failure* every pass → 0 blocks cached → 900s stall.

The mechanism (traced through `llm_invocation.py` + `layer4/per_phase.py`):
- Each block runs a **two-step escalation**: a stochastic **thinking attempt** (`temp=1.0`, `tool_choice=auto`, ceiling = `effective_max_tokens + thinking_budget`), then a deterministic **forced-tool retry** (thinking OFF, `tool_choice=forced`, ceiling = `effective_max_tokens` **alone** — no `+thinking_budget` headroom).
- Block-mode sizing was `effective_max_tokens = 14 × _BLOCK_OUTPUT_TOKENS_PER_SESSION(900) + _BLOCK_OUTPUT_TOKENS_OVERHEAD(1200) = **13,800**`.
- But prod telemetry (pv=39) measured blocks emitting **10–16k** output tokens. So the forced-retry ceiling (13,800) sat **below the worst case** → truncation.
- **Why pv=39 passed and pv=40 failed on the same inputs:** the `temp=1.0` thinking attempt is a coin-flip. pv=39 got a complete tool call out of step 1 and never leaned on the undersized step-2 fallback; pv=40's step-1 fell through to the forced retry, which truncated. The forced retry was supposed to be the *reliable floor* and wasn't.

This is the **same class** as the pv=38 truncation fix (which raised 600→900) — the constant was still short of reality.

### The fix (PR #327)

Raised the per-block output sizing so the forced retry reliably clears a worst-case dense week:

| constant (`layer4/per_phase.py`) | before | after |
|---|---|---|
| `_BLOCK_OUTPUT_TOKENS_PER_SESSION` | 900 | **1400** |
| `_BLOCK_OUTPUT_TOKENS_OVERHEAD` | 1200 | **2000** |

→ `14 × 1400 + 2000 = **21,600**`, ~35% over the observed 16k worst case. `max_tokens` is only a ceiling — billed/latency cost tracks tokens actually emitted, and the `_PER_BLOCK_BUDGET_MS=120_000` guard still bounds synthesis time — so the headroom is effectively free.

1 code file (`layer4/per_phase.py`) + 1 test (`tests/test_layer4_plan_create.py`, the block-mode assertion `13800 → 21600`; the computed-from-constants assertion already tracks). **Full suite: 1993 passed / 16 skipped.** No migration.

---

## 2. Issues / state

- **#324** (open) — plan-gen completion blocker. Its **resilience half is #325** (shipped, but see the design-flaw note below); its **truncation half is now fixed by #327**; its **latency half is #316**.
- **#316** (open, `status:designed`) — the per-week pre-compute periodization grid (the latency cure). **Andy's call: pre-compute, not shrink blocks.** Unchanged.
- **#325 design flaw exposed (not yet filed/fixed):** retrying a **deterministic** `schema_violation` is futile — #325 converted what used to be a **fast, loud** failure (`Plan synthesis failed (schema_violation)` in ~4 min, real code surfaced) into a **15-min silent stall** ending in a generic "contact support" message that *buries* the real error. The retry has no per-block cap; it leans entirely on the 900s wall-clock. A `_RETRYABLE_BLOCK_CODES` retry should be bounded (e.g. fail fast after N deterministic repeats) and surface the underlying code. **Deferred — Andy's call whether to fix now or after re-verify.**
- **Cap-config drift (latent, not what failed pv=40):** `_INVOCATION_BUDGET_S = max(_FUNCTION_CAP_S(300) − _INVOCATION_RESERVE_S(330), 30.0)` floors to **30s** because #325's reserve bump (255→330) was sized against the **800s** cap the comments reason about, but the live dashboard cap is **300s** (`CLAUDE.md` env ref). The budget gate never fired in pv=40 (the first synthesis is never gated, `per_phase.py:706` `synth_count[0] >= 1`), so this did **not** cause the failure — but `reserve > cap` is a silent misconfiguration that wants a guard (assert/clamp `reserve < cap`, or reconcile the 800-vs-300 comments). **Deferred.**

---

## 3. Key facts captured this session

- pv=40 failure = **first-block output truncation** at the forced-tool retry, deterministic, masked on pv=39 by the stochastic thinking attempt. NOT a data/schema-shape fault; NOT the #319 canon cleanup.
- The forced-tool retry's ceiling is `effective_max_tokens` **alone** — this is the sizing that must clear the worst case, not the thinking-attempt ceiling.
- #325's block-fumble retry is correct for *transient* fumbles but wrong for *deterministic* ones (it stalls instead of failing fast).
- The 800s-cap reasoning in `routes/plan_create.py` comments is stale vs the live 300s dashboard cap.

---

## 4. Open / owed / next

**Owed (Andy's hands): the single most important next action — re-verify with PR #327 live.** Generate a fresh PGE 2026 plan on the new deploy and confirm it **reaches `ready`** (or at least caches blocks past the first). #327 should let the first block (and every dense block) serialize without truncating.
- **If it completes** (even slowly, ~20–30 min) → plan-gen is **functional**; the go-live blocker is cleared; #316 becomes a schedulable speed/UX optimization.
- **If it gets further but stalls again** → that's the **latency** wall (a legit ~16k block still runs ~200–249s against the **300s** cap), i.e. #316 territory — *not* truncation. The admin inspect + per-block metadata will show block count + `cap_hit`/`retries_used`.
- **If it stalls at 0 blocks again** with a *different* `detail` → send back the `_advance_plan_generation: Layer4 … (schema_violation) … : <detail>` line; a new failure mode.

**Then, Andy's call (deferred this session):**
1. **Harden #325** — bound the deterministic-retry so a repeating `schema_violation` fails fast + surfaces the real code, instead of a 15-min generic stall. (Would have turned pv=40's mystery into a 4-min clear error.)
2. **Cap-drift guard** — `reserve < cap` assert/clamp + reconcile the 800-vs-300 comments.
3. **#316** — the pre-compute grid, only if 20–30 min generation is too slow for the timeline.

**Do NOT pre-build #316 or the #325 hardening** — re-verify #327 first; the result decides their urgency.

---

## 6.3 Operating notes — session-start reads (Rule #13)

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling carry-state (owed = the #327 re-verify run).
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.

**First move next session:** the #327 re-verification run (above), unless Andy redirects. Plan-gen completion (#324/#316) remains the live go-live blocker; canon/observability/data work is done and validated; truncation is now fixed pending the proof run.

---

## 8. Verification table (Rule #10 — file:line anchors for the next Rule #9 sweep)

| Claim | File | Anchor / check |
|------|------|------|
| Per-session output budget raised 900→1400 | `layer4/per_phase.py` | `_BLOCK_OUTPUT_TOKENS_PER_SESSION = 1400` |
| Block overhead raised 1200→2000 | `layer4/per_phase.py` | `_BLOCK_OUTPUT_TOKENS_OVERHEAD = 2000` |
| Dense-week ceiling now 21,600 | `layer4/per_phase.py` | `effective_max_tokens = max(max_tokens, max_sessions_this_unit * _BLOCK_OUTPUT_TOKENS_PER_SESSION + _BLOCK_OUTPUT_TOKENS_OVERHEAD)`; 14×1400+2000 |
| Test tracks the new ceiling | `tests/test_layer4_plan_create.py` | `test_block_mode_scales_max_tokens_to_session_ceiling` asserts `mt == 21600` (computed from the constants) |
| Forced-retry ceiling is `effective_max_tokens` alone | `llm_invocation.py` | the `_attempt(0)` (thinking-off) call after a failed thinking attempt; `request_kwargs["max_tokens"] = max_tokens` (no `+ thinking_budget`) |
| First synthesis never gated by budget | `layer4/per_phase.py` | `if synth_count[0] >= 1 and generation_deadline_passed()` (gate skips the first block) |
| Stall backstop = 900s since last cached block | `routes/plan_create.py` | `_STALL_WALLCLOCK_S = 900`; `_generation_stalled` measures since most-recent block |
| pv=40 failure code path | `routes/plan_create.py` | `_RETRYABLE_BLOCK_CODES` includes `schema_violation`; the `isinstance(exc, Layer4OutputError) and exc.code in _RETRYABLE_BLOCK_CODES` branch returns `'generating'` (the deterministic-retry-into-stall path) |

Full suite at session end: **1993 passed / 16 skipped**. PR #327 merged to `main` (merge commit `ecee04e`).
