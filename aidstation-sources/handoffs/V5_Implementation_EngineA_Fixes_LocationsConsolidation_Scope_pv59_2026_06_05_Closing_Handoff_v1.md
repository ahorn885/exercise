# V5 Implementation — Engine A fixes (#423) + pv=59 equipment root-cause (vocabulary mismatch) + Locations/Layer-4/D-52 redesign scoped, slice A0 shipped

**Date:** 2026-06-05
**Branch:** `claude/amazing-thompson-FIfxN`
**PR:** #425 — **CI green; merged to `main`.** Contents: Engine-A latency-accounting fix + `extended_thinking_budget=0`; `Locations_Consolidation_Design_v1.md` (Track 1 spec); `dedupe_layer0_equipment_items.sql` (slice A0).
**Issues:** Engine A = **#423** (this session's fixes). The redesign is a new 3-track program (see §4) — file as an epic next session.

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch 403s (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. Untruncated runtime logs: Vercel dashboard (team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`); the runtime-log MCP truncates the message column (Rule #14).

---

## 1. What this session was

Monitored a fresh cold PGE plan (**pv=59**, post-#316-grid deploy) via the diag token. It **failed** (D-77 stall backstop) at **`Build:w1`** with 2 blocks cached (`Base:w1`, `Base:w2`). Andy then steered into a full redesign of the locations + Layer-4 synthesis model. Two distinct outcomes:

### 1.1 Engine A confirmed + fixed (#423)
Untruncated logs on `Build:w1` (Andy pasted): `record_phase_sessions attempt (thinking=5000) 436865ms outcome=no_tool_use_block out_tokens=26600/26600 stop_reason=max_tokens` → forced retry `(thinking=0) 115982ms tool_use_ok`. The **thinking-first attempt burned 437s to `max_tokens` with no tool block**, then the forced retry did the real work in 116s. That + the next attempt overran the 800s cap. Two coupled defects:
- **Latency undercount:** `invoke_tool_call` returned only the *winning* attempt's latency (~116s), so the per-block budget guard (`_PER_BLOCK_BUDGET_MS`) never saw the wasted 437s and green-lit a doomed next attempt → 504. **Fixed:** accumulate wall time across every `_attempt` (`latency_acc`).
- **The thinking attempt is pure overhead** on dense weeks. **Fixed:** `DEFAULT_EXTENDED_THINKING_BUDGET = 5000 → 0` (per_phase.py:79) — `invoke_tool_call` goes straight to the forced tool (one ~116s call, all of `max_tokens` as output). Seam reviewer keeps its own `seam_thinking_budget` (independent constant). Tests: 47 invocation/thinking + 189 layer4 suite green.

**The grid (#316) verdict:** `Build:w1` attempt-1 validation showed **one** `volume_band_below_week_1_D-009_build` blocker (down from pv=58's **three**) — improved, but the correction loop never ran attempt 2 (Engine A ate the budget), so the grid can't be fully cleared until Engine A is fixed. With #423 in, the next cold plan is the real grid test.

### 1.2 pv=59 `equipment_unavailable` — VERIFIED root cause = vocabulary mismatch (NOT missing data)
`Build:w1` also threw `equipment_unavailable_SQ-001_at_home` / `…_SL-001_at_home`. Earlier sessions blamed missing/stale equipment data. **Verified false (code+tests):** Layer 2C resolves `exercises.equipment_required` in **layer0 canonical names** (Title-case, e.g. `"Squat rack"` — `tests/test_layer2c.py:329`), but `orchestrator._q_locale_equipment_pool` returns **`public.equipment_items.tag`** (snake_case, `"squat_rack"`) with no conversion → `_tier_1`'s `issubset` **never matches** → every equipment-requiring exercise fails `equipment_unavailable`, regardless of saved gear. Bodyweight exercises (empty `equipment_required`) resolve — why Base weeks partially banked. **This is the real pv=59 equipment failure.**

---

## 2. Shipped (PR #425 — merged)

- **`llm_invocation.py`** — `latency_acc` cumulative latency across attempts (the budget guard now sees true wall time).
- **`layer4/per_phase.py`** — `DEFAULT_EXTENDED_THINKING_BUDGET = 0` (skip the thinking-first attempt for block synthesis).
- **`aidstation-sources/Locations_Consolidation_Design_v1.md`** — Track 1 spec (see §4).
- **`etl/sources/dedupe_layer0_equipment_items.sql`** — slice A0 (see §3, §5).

## 3. The redesign (Andy's architecture direction, 2026-06-05)

> "We shouldn't be blocking plan-gen when something like that fails. The deterministic work should prevent something that won't work from ever getting to the LLM. Determinors produce a feasible, pre-computed input set; the LLM synthesizes — it doesn't figure out the determinism."

Equipment/volume/injury feasibility moves OUT of the LLM (it's deciding things determinism should own; the validator blocks + forces expensive retries). The pieces mostly already exist (2C `effective_pool`, `periodization.py`, 2D injury filter, per-discipline hour bands) — they're advisory, not authoritative. Locked decisions:
- **Intensity split + rest-day placement + session allocation → deterministic.** Rest days = disabled `daily_availability_windows`. Sport-priority → a **numeric** transform of the existing Critical/High/Med/Low (no new column; `_STRENGTH_PRIORITY_RANK` already half-does it).
- **LLM's remaining job:** organize the week so strength fits the other disciplines' work, picking from a ranked feasible pool. Guided, never failing.
- **Validator:** feasibility rules → defensive asserts/warnings, not retry-driving blockers.

## 4. The 3-track program (sequenced by overlap; go-live-blocker first)

- **Track 1 — Locations Consolidation** (`Locations_Consolidation_Design_v1.md`, spec'd). Drop legacy (`locale_equipment`, `_edit_legacy_locale`, the `home` enum); **every** locale on the `gym_profiles` + overrides model; `home` = `locale_profiles.preferred` (required invariant, atomic single-home, first-locale-auto-home); `private` = `gym_profiles.private` (crowd-sourcing exclusion only); multi-locale **cluster** = home + saved locales within **26.2 mi / 42.2 km** (manual out-of-radius add deferred). **Canonical-direct (Andy concurred):** picker reads `layer0.equipment_items` directly, store holds **canonical names**, `_q_locale_equipment_pool` returns them to 2C — **no alias table**, the public tag vocab retires. ONE authoritative `locale_effective_tags` in a new `locations.py` (UI + plan-gen both call it).
- **Track 2 — Determinism-first Layer 4 synthesis** (NOT yet specced — spec just-in-time per the "spec what we're about to build" rule). Make the feasible pool authoritative (tool-schema-constrain `exercise_id` ∈ pool ∖ 2D-excluded); new deterministic session-allocation + intensity stages; **wire `rx_engine`** (currently strength-only/post-hoc — the synthesizer never reads `current_rx`); demote feasibility validator rules.
- **Track 3 — D-52 full catalog migration** (`Catalog_Migration_Plan_v3.md`, 5 phases exist). Retire `public.exercise_inventory` → `layer0.*`, move `rx_engine` + 7 v1 routes onto layer0, per-user FK (wipe pattern — 1–2 test accounts), drop `public.*`. **Equipment slice is on the critical path** (it's what fixes pv=59); the **exercise-catalog bulk is parallel/after** — NOT a plan-gen blocker (v2 already reads layer0 exercises via 2C; only the equipment side is mis-wired).

**Sequence:** A (equipment-canonical) → Track 1 → Track 2 → D-52 exercise-catalog bulk.

## 5. Owed (Andy's hands — Neon egress blocked from the container)

1. **Run `etl/sources/dedupe_layer0_equipment_items.sql` on Neon** (slice A0). Collapses ~15 exact-duplicate active `equipment_items` rows + 3 case-variant pairs (`Pinch Block`/`Pinch block`, `Trekking Poles`/`Trekking poles`, `Wrist Roller`/`Wrist roller`), rewrites `exercises.equipment_required`, adds a partial unique index `(lower(canonical_name)) WHERE superseded_at IS NULL`. Idempotent. Watch the final `NOTICE` for residual Title-case variant refs in the JSONB substitute/proxy columns (review if >0).
2. **(After Track 1 A1 lands)** run the Track-1 DDL (drop `locale_equipment` + `locale_profiles.equipment` + one-home index), **re-enter Home gear** in the new canonical picker, mark it `home`, **re-run a cold PGE plan**. Win: no `equipment_unavailable`, no `volume_band` blockers on Build/Peak/Taper, no Engine-A 504, blocks → `ready`.

## 6. Next move

Build **Track 1 / A1** (canonical-direct code), slices: (1) `locations.py` authoritative `locale_effective_tags`/`cluster_locale_ids` (canonical names) + unit tests; (2) orchestrator rewire (`_q_primary_locale`→`preferred`, `_q_locale_equipment_pool`→module, cluster un-stub); (3) equipment picker → `layer0.equipment_items`; (4) drop legacy + one-home index + residential `private=TRUE`; (5) rewire `references.py`/`list_profiles`/city lookups. Code is unit-testable from the container; live pv=59 proof needs the owed Neon runs (§5). Then spec + build Track 2; D-52 exercise-catalog bulk in parallel. **File the 3-track program as a GitHub epic.**

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 7. §6 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Latency accumulates across attempts | `llm_invocation.py` | `grep -n "latency_acc" llm_invocation.py` |
| Thinking budget 0 for block synth | `layer4/per_phase.py` | `grep -n "DEFAULT_EXTENDED_THINKING_BUDGET = 0" layer4/per_phase.py` |
| Vocab mismatch (pool vs 2C) | `layer4/orchestrator.py` / `tests/test_layer2c.py` | `_q_locale_equipment_pool` returns `ei.tag`; 2C tests use `"Squat rack"` (test_layer2c.py:329) |
| Track 1 spec | `aidstation-sources/Locations_Consolidation_Design_v1.md` | `grep -n "canonical-direct\|VERIFIED ROOT CAUSE" Locations_Consolidation_Design_v1.md` |
| A0 dedupe migration | `etl/sources/dedupe_layer0_equipment_items.sql` | `grep -n "equipment_items_active_ci_name_idx" etl/sources/dedupe_layer0_equipment_items.sql` |

---

## 8. Test / verification state
- `tests/test_llm_invocation_timeout.py` + `test_layer4_thinking_request.py` + `test_layer3_thinking_request.py`: **47 passed**. `test_layer4_thinking_request.py` + `test_layer4_periodization.py` + `test_layer4_plan_create.py` + `test_routes_plan_create.py` + `test_llm_invocation_timeout.py`: **189 passed**. No DB/LLM run from the container (Neon egress blocked) — the cold re-run (§5) after the owed Neon work is the real proof.

*End of handoff.*
