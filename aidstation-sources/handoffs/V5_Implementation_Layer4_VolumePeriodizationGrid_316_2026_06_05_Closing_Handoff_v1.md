# V5 Implementation — Layer 4 per-week volume periodization grid (#316, the real `volume_band` fix) + pv=58 stall root-cause

**Date:** 2026-06-05
**Branch:** `claude/quirky-volta-rcjOo`
**PR:** #422 (this session — the per-week periodization grid + the stale-cap comment refresh). **CI green; squash-merged to `main`.**
**Issues:** **#316 closed `completed`** (the grid IS the real `volume_band` fix it specced); **two follow-ups filed** — the synthesizer extended-thinking-first runaway (latency) and the grid's v2 3A coupling.

---

## ⚡ Diagnostic token (read this first — used every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```

Read any plan's state past the login wall:
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc`

- WebFetch gets a **403** (Vercel deployment protection) — fetch via the **Vercel MCP `web_fetch_vercel_url`** tool, which authenticates.
- Per-minute `GET /plans/v2/cron/generate-pending` is the #416 seam heartbeat: it spends **LLM tokens only when it actively advances a pending plan**; while the advance-lock is held or nothing is pending it returns 200 as a **no-op (zero tokens)**. Idle ticks cost negligible Vercel compute, not model tokens.
- Runtime-log MCP **truncates the message column** + full-text search gives unreliable negatives (Rule #14). For a full line (`llm_layer3a … HIT/MISS ibundle=…`, `synthesize_phase …`, `record_phase_sessions attempt …`) pull from the **Vercel dashboard**. Team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`.

---

## 1. What this session was

Andy raised `PLAN_GEN_FUNCTION_CAP_S` to **800** and re-ran a fresh cold PGE plan (**pv=58**) to exercise the #335 strength fix. I monitored it via the diag token. It **stalled at `Build:w2`** (1 of ~6 blocks cached → 800s `FUNCTION_INVOCATION_TIMEOUT` → D-77 stall backstop → `failed`).

Pulling the **untruncated Vercel logs** (Rule #14 — after I twice mis-theorized from the diag alone) root-caused it precisely, and the read is two independent engines:

- **Engine A — each failed attempt is enormous.** The per-phase synthesizer's FIRST attempt runs with `extended_thinking_budget=5000` + `tool_choice:auto` (`llm_invocation.invoke_tool_call`); on `Build:w2` the model burned the entire `21,600+5,000=26,600`-token ceiling thinking (`stop_reason=max_tokens`, no tool block) — **418s of dead time** — then the forced-tool retry (thinking off) did the real work in **110s**. The per-block budget guard (`_PER_BLOCK_BUDGET_MS=120s`) gates only retries, so a single uninterruptible first attempt ≈ 530s; two blocks' first attempts in one pass > 800s → 504, nothing committed past the in-flight block.
- **Engine B — attempts keep FAILING validation.** `volume_band` graded each week against a **flat per-phase band** while the prompt told the model to ramp/deload/taper — so `Build:w2` came back with **per-discipline blockers** (`volume_band_above_week_2_D-001`, `below_week_2_D-003`/`D-009`): the model mis-split the fixed weekly hour budget (over-fed one sport, starved two), AND a legitimate ramp would have tripped the flat band anyway.

**This session fixed Engine B — #316, the per-week periodization grid** (the data problem). **Engine A (the thinking-first runaway) Andy explicitly deferred** ("no time-limit work until the data problem is sorted") → filed as a follow-up issue.

Corrections to my own earlier diag-only theories (logged for the record): the cone was a **clean HIT** (`llm_layer3a/3b/l4_cached/block-0 HIT` — NOT a re-compute / layer-2B drift), and the advance-lock leak was **downstream** mechanics, not the primary cause. The real driver is Engine A consuming the 800s budget while Engine B forces the retries.

---

## 2. Shipped (PR #422 — 3 commits, all green; NO migration)

### Stale-cap comment refresh (commit 1)
`layer4/per_phase.py`: the `_PER_BLOCK_BUDGET_MS` docstring + 3 diagnostics asserted an "immovable 300s Vercel cap." Reframed to the configurable `PLAN_GEN_FUNCTION_CAP_S` (300s default / 800s Pro) so it can't re-stale, and recorded the first-attempt-ungated caveat. Comments only.

### The per-week volume periodization grid — #316 (commits 2–3)
- **New `layer4/periodization.py`** — the single source of truth for the per-`(phase, week_in_phase)` volume multiplier, so the band, the prompt target, and the `recovery_week` flag can never disagree. Curve (signed off 2026-06-05 — see `Layer4_VolumePeriodizationGrid_Design_v1.md`):
  - Deload cadence mode-dependent (`_DELOAD_CADENCE_WEEKS`: standard 4 / compressed 3 / extended 5; mirrors `per_phase._DELOAD_CADENCE`); depth `_M_DELOAD=0.55` (~45% cut).
  - Loading ramp `_RAMP_STEP=0.08` (~8%/wk), the counter **resets at each deload** → a 3:1 sawtooth; coming out of a deload returns to baseline, not straight to peak.
  - **Base/Build/Peak are volume-neutral** (per-week multipliers renormalized so the phase mean = 1.0 → the 2A phase total is preserved). **Taper is the exception** — a deliberate Bosquet-2007 descent (`0.75 / 0.60 / 0.40` by weeks-from-end, intensity held), NOT renormalized.
  - Grounded in the deloading / ACWR / Bosquet taper literature (design note §4, cited).
- **Validator** (`validator.py`): new `phase_week_volume_bands_hours()` (flat band × the grid multiplier); `_rule_volume_band` grades each week against its own week band. `above`/`below` are now **symmetric** — the interim flat-band Peak/Taper/`recovery_week` `below`→warning demotion is **removed** (a deload/taper week is simply inside its lower band). Degrades to the flat band when `phase_structure` can't resolve the week.
- **Synthesizer prompt** (`per_phase.py` `_format_phase_load_bands`): renders a **concrete per-week, per-discipline target + tolerance** instead of a flat range — the anchor that stops the model mis-splitting the weekly hour budget (the `Build:w2` allocation error).
- **`recovery_week` stamper** (`per_phase.synthesize_phase` → `periodization.stamp_recovery_week`): stamps `recovery_week` on planned-deload weeks, the **§8.1 orchestrator step that was documented but never implemented** (`validator.py` had a forward-looking reader that never fired). Shares the grid's deload cadence.

**v1 is athlete-agnostic; 3A coupling (`recent_trajectory`/`data_density`/ACWR modulation) is a committed v2 follow-up** (filed as an issue).

---

## 3. The pv=58 diagnosis (for the record)

- **Kill = 800s `FUNCTION_INVOCATION_TIMEOUT`**, after `Build:w2`'s first attempt (418s thinking runaway + 110s forced retry) plus the next block's first attempt overran. `cached_blocks=1`, `next_block_index=1`.
- **`Build:w2` validator (untruncated log):** `volume_band_above_week_2_D-001_build(blocker)`, `volume_band_below_week_2_D-003_build(blocker)`, `volume_band_below_week_2_D-009_build(blocker)` + intensity-drift warnings + `equipment_unavailable`. The grid fixes the volume-band trio at the source.
- **The runaway line:** `record_phase_sessions attempt (thinking=5000) 418294ms outcome=no_tool_use_block out_tokens=26600/26600 stop_reason=max_tokens` → forced retry `(thinking=0) 110480ms outcome=tool_use_ok`. This is Engine A, deferred to the follow-up issue.

---

## 4. Carry-forward (deferred; details in `CARRY_FORWARD.md` + the new issues)

- **Synthesizer extended-thinking-first runaway (Engine A) — NEW ISSUE, the next lever now that the data problem is solved.** Drop `extended_thinking_budget` to 0 for block synthesis (go straight to the forced tool — the retry already does the real work in ~110s), and/or gate the first attempt / reserve headroom so a pass never starts a block it can't finish under the cap. Each failed attempt costs ~530s until this lands.
- **Grid v2 — 3A coupling — NEW ISSUE (committed).** Modulate the ramp steepness by 3A `recent_trajectory` / `data_density` (conservative ramps for sparse data, §8.2) / ACWR. v1 ships the deterministic athlete-agnostic curve.
- **#335 Slice 3** (3A-strength-state dose modulation) + Phase 2b `rx_engine` absolute loads — still open from the prior session.
- **Advance-lock TTL vs function duration** — still on the list (a 504'd pass leaks its ~749s lock; survivable now that blocks commit faster once Engine A is fixed, but worth aligning).

---

## 5. Owed + next moves

### 5.1 Owed deploys
- **NONE.** No migration (the grid reads existing inputs — 2A bands, capacity, `week_in_phase`, phase weeks/order via `phase_structure`). Merging PR #422 → `main` redeploys prod via the git-main alias.
- **Expected on the first post-merge cold plan:** a one-time **cold re-synth** of the per-phase blocks — the prompt-text change (per-week targets) shifts the content-addressed synthesizer cache key. Expected, not a regression. The cone still HITs.

### 5.2 Next move — the cold-plan re-run (Andy, after the deploy)
Kick a fresh cold PGE plan, monitor via the diag token. **Win conditions:**
1. **No `volume_band_*` blockers on Build/Peak/Taper weeks** — each week graded against its own bent band (check `blocks[].synthesis_metadata` / runtime `validator rejected` lines).
2. **`recovery_week` appears on deload weeks** (every 4th plan-global week in standard mode).
3. **`blocks_snapshotted` climbs toward `ready`.**
- **Caveat:** Engine A is NOT fixed this session, so `Build:w2` (and any dense week) may still burn ~418s on the thinking-first attempt → a pass could still 504 before banking 2 blocks even though the *validation* now passes. If it stalls again, that's Engine A (the deferred issue), not the grid — confirm via the runtime `record_phase_sessions attempt (thinking=5000) …max_tokens` line. The grid's success is measured by the **absence of `volume_band` blockers**, independent of whether the run completes.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

---

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Grid module + curve params | `layer4/periodization.py` | `grep -n "_M_DELOAD\|_RAMP_STEP\|_DELOAD_CADENCE_WEEKS\|def phase_week_multipliers" layer4/periodization.py` |
| Validator grades per-week band | `layer4/validator.py` | `grep -n "phase_week_volume_bands_hours\|week_volume_multiplier" layer4/validator.py` |
| Demotion removed (symmetric) | `layer4/validator.py` | `grep -n "SYMMETRIC\|interim flat-band patch" layer4/validator.py` (the old `is_recovery_week` demotion is gone) |
| Prompt feeds per-week targets | `layer4/per_phase.py` | `grep -n "Per-week volume targets\|hr target" layer4/per_phase.py` |
| recovery_week stamped | `layer4/per_phase.py` | `grep -n "stamp_recovery_week" layer4/per_phase.py` (called before the `PhaseSynthesisResult` return) |
| Cap reasoning refreshed | `layer4/per_phase.py` | `grep -n "PLAN_GEN_FUNCTION_CAP_S" layer4/per_phase.py` |
| Grid unit tests | `tests/test_layer4_periodization.py` | `grep -n "volume_neutral\|stamp_recovery_week" tests/test_layer4_periodization.py` |
| Design note (signed off) | `aidstation-sources/Layer4_VolumePeriodizationGrid_Design_v1.md` | `grep -n "SIGNED OFF" Layer4_VolumePeriodizationGrid_Design_v1.md` |

---

## 7. Test / verification state

- Full `tests/test_layer4_*.py`: **875 passed** (in-container, 2026-06-05). New `tests/test_layer4_periodization.py` (grid math + stamper); `test_layer4_validator.py` volume-band cases re-baselined to the grid (threshold tests pinned to a 1-week unit structure; removed-demotion tests replaced with grid-behavior coverage).
- No live-DB / LLM run from the container (Neon egress blocked) — the cold-plan re-run (§5.2) is the real proof.

---

*End of handoff.*
