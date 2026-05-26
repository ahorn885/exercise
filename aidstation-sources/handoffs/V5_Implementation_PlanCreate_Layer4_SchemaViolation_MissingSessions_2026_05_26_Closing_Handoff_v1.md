# plan-create Layer 4 per-phase schema_violation (missing `sessions` array) — retry + instrument + over-emit clamp — Closing Handoff

**Session:** Diagnosed a **new** live "Plan generation didn't finish — Plan synthesis failed (schema_violation)" report. Unlike the #179/#181 chain (which was **Layer 3A**, "Athlete evaluation failed"), this one is **Layer 4** — the cone now clears 3A and dies one layer down at per-phase synthesis. Pinned it via the #180 Layer4-detail log + the Vercel runtime-log full-text elimination to a `Layer4OutputError(schema_violation)` raised at `layer4/per_phase.py:1334` because the per-phase synthesizer returned a tool_use block whose `tool_args` carried **no `sessions` array**. Fixed with the Andy-approved "retry + instrument" approach (treat missing-`sessions` like the parse-failure path 15 lines below — retry within the cap, raise terminal only after exhaustion; log the keys the model DID emit), and folded in the over-emit clamp (`_clamp_sessions_over_emit`). Root cause: a **retry asymmetry** — missing/non-list `sessions` hard-raised on the first miss while the structurally-identical parse-failure path retried up to `capped_retries=2`.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_PlanCreate_Layer3A_SchemaViolation_ObservationText_2026_05_26_Closing_Handoff_v1.md` (PR #181 `ea00f5e`; #180 `03a3e46` added the Layer4/Layer3 detail logging that made this diagnosable — same elimination method)
**Branch:** `claude/plan-generation-schema-error-Sn7cO`
**Status:** 1 substantive code file (`layer4/per_phase.py`) + 1 test file (`tests/test_layer4_plan_create.py`) + bookkeeping. Full suite **1729 passed / 16 skipped** (+5 over the 1724 baseline).

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| PR #181 merged (`ea00f5e`) on `main` | `git log` | ✅ present; branch base |
| `_clamp_observation_text` present in 3A/3B (the #181 fix) | grep | ✅ (3A no longer the failing locus — confirmed by the live error moving to Layer 4) |
| #180 added the Layer4 detail log to the `Layer4*Error` catch at `routes/plan_create.py:253-257` | read | ✅ — that log is what pinned this |

Andy reported the live symptom directly ("Plan synthesis failed (schema_violation)" on a fresh plan-gen), so the session was bug-driven.

## 2. Session narrative

The athlete-facing string `Plan synthesis failed ({exc.code})` is built at `routes/plan_create.py:260` — the typed Layer 4 catch (`Layer4InputError | Layer4OutputError`). This is a **different** message from the 3A "Athlete evaluation failed" the #179/#181 chain fixed; the failure has moved one layer down.

Diagnosed via the **Vercel runtime-log MCP** by the predecessor's whole-token elimination method. On the failing requests (`POST /plans/v2/21/generate` + two `generate-pending` crons, ~17:47–17:51, deployment `dpl_CZG4BUBhK1XUahC36EGQiAQK5xkw`):
- `Layer4OutputError` **matches**; `Layer4InputError` **does not** → output-side.
- `tool args missing` **matches cleanly** (no timeout warning); `did not parse` and `no synthesizer pass` **do not** → the locus is `per_phase.py:1334` (`detail="tool args missing 'sessions' array"`), **not** the PlanSession-parse path (1352) or the no-pass path (1426).

(Note: negative log results that carry a "query timed out before all pages were fetched" warning are **unreliable** — the search aborted. Only clean negatives and any positive match are trustworthy. `tool args missing` ✅ and `no synthesizer pass` ✗ were both clean.)

**Root cause.** The per-phase synthesizer runs under extended thinking (`DEFAULT_EXTENDED_THINKING_BUDGET=5000`, `DEFAULT_MAX_TOKENS=4000`, so `tool_choice: auto` per the `invoke_tool_call` invariant). Under `auto` the model can emit a thin/partial tool call. When it returns a tool_use block whose args lack a valid `sessions` list, `per_phase.py:1334` **hard-raised on the first miss** — even though `capped_retries=2` retries were available and unused. The parse-failure path immediately below (1350-1366) already does the right thing (record a `RuleFailure`, re-prompt, retry, raise only at the cap); the missing-`sessions` case was the asymmetric outlier.

(Separately noticed, NOT fixed here: recurring `504`s on the `generate-pending` cron — Vercel function-duration / `max_tokens` truncation. Distinct from this schema_violation; partly covered by the async-progress/timeout + cron-background handoffs. Flagged so it's not conflated.)

Andy approved (AskUserQuestion): fix = **retry + instrument**; scope = also fold in the over-emit clamp (#2); and he wants the larger #1/#4/#5 slices done too (deferred to their own scope — see §6).

## 3. File-by-file edits

### 3.1 `layer4/per_phase.py` (modified)
- New `_MAX_SESSIONS_PER_PHASE = 56` constant (lock-step with the `maxItems` passed to `build_record_phase_sessions_tool`; doc-comment notes the schema bound is only an API hint).
- `tool_schema = build_record_phase_sessions_tool(_MAX_SESSIONS_PER_PHASE)` (was the bare default — now explicit + lock-step).
- New `_clamp_sessions_over_emit(raw_sessions, phase_name)` pure helper — trims over-count to the ceiling pre-validation, passes through at/under, logs when it fires. (Extracted as a helper so it's unit-testable, matching the 3A/3B `_clamp_*` precedent.)
- **The core fix**, in the synthesis loop: the `if not isinstance(raw_sessions, list):` block no longer hard-raises. It now logs the keys the model emitted (`synthesize_phase: <phase> pass N returned no 'sessions' array (tool_args keys=[...])`), then — mirroring the parse-failure path — raises `Layer4OutputError("schema_violation", ...)` **only when `current_pass >= capped_retries`**; otherwise records a `schema_violation` `RuleFailure` (severity blocker) + `continue`s to the next pass. The terminal detail now includes the attempt count + the emitted keys.
- The over-emit clamp is called right after the (now retry-aware) missing-`sessions` guard, before the `_build_plan_session` parse loop.

### 3.2 `tests/test_layer4_plan_create.py` (modified)
- Import `Layer4OutputError` (was only `Layer4InputError`).
- New `TestMissingSessionsRetry` (3 tests): missing `sessions` key → retry → succeeds (via `_phase_seq_stub([{no sessions}, _empty_phase_output()])`); explicit `sessions: None` → same retry path; all-passes-miss → terminal `Layer4OutputError(code="schema_violation")` with `"sessions"` in the detail.
- New `TestSessionsOverEmitClamp` (2 tests): `_clamp_sessions_over_emit` trims `> ceiling` to the ceiling; passes through at-cap and under-cap unchanged.

## 4. Code / tests

Full suite **1729 passed / 16 skipped** in a fresh `/tmp/venv` (+5 over the 1724 baseline). `py_compile` clean. (DB egress to Neon blocked from the container; PyPI egress works — note `pytest` is **not** in `requirements.txt`, `pip install pytest` into the venv. The isolated-collection circular-import quirk still applies: run the full `tests/` or front-load a `tests/test_layer4_*.py`.)

## 5. Owed action (Andy's hands)

**None for code** — no migration (code-only). The per-phase **prompt body is unchanged**, so the 3A/3B/per-phase content-addressed cache keys are **stable** (no forced re-run). The live test: a fresh `/plans/v2/new` for PGE 2026 — per-phase synthesis no longer `schema_violation`s on a thin tool call (it retries within the cap; the Vercel log shows `synthesize_phase: <phase> pass N returned no 'sessions' array (tool_args keys=[...])` on a miss). **Confirm Andy's profile has `body_weight_kg` + `height_cm`** — else 2E still raises the *named* `Layer2EInputError` (still blocks). Stale failed rows (e.g. plan 20/21) stay terminal — start a fresh plan.

## 6. Next session pointers — the deferred slices Andy approved

Andy approved doing all four; each needs its own scope (the 5-file ceiling + spec-first/stop-and-ask rules mean they don't belong in this PR). Recommended order:

### 6.1 (#2 — DONE this session) sessions[] over-emit clamp ✅
Shipped (`_clamp_sessions_over_emit`). The remaining un-clamped Layer-4 bounded arrays (`plan_refresh.py:391`, `single_session.py:269`, `seam_review.py:137`, `race_week_brief.py:401` `kit_manifest`) are **lower-risk** — their pydantic models (`PlanSession`, `RaceWeekBrief`, `RacePlan`) carry no `max_length`/`max_items` and `plan_sessions.payload_json` is JSONB with no CHECK, so over-emit there doesn't hard-fail. Apply the same `_clamp_*` pattern if any surfaces.

### 6.2 (#1) `Layer4ShapeInfeasibleError` — spec'd, not in code
`grep -rn "Layer4ShapeInfeasibleError" --include=*.py` → 0 hits; spec'd in `Layer4_Spec.md` §10.2 with **four** detection classes (`schedule_volume_infeasible`, `discipline_frequency_infeasible`, `skill_acquisition_infeasible`, `cumulative_load_injury_infeasible`), each a pure-function check evaluated after `phase_structure_from_3b()` and before per-phase synthesis (TS-10..TS-13). **Has an OPEN routing decision** (spec finding C3 / §12.3): surface as an inline athlete-facing error in the current run, or as a 3D HITL gate item for the next run? Spec recommendation: inline for the current run, 3D as next-run backup. **This is stop-and-ask (#3 cross-layer + #5 open architectural choice)** — pin the routing with Andy first. Couples to #4 (3D is one routing target). Without it, the shape-infeasible condition falls to the `routes/plan_create.py:305` catch-all → opaque terminal `failed`.

### 6.3 (#4) Layer 3C / 3D / 3.5 HITL gate — designed, not implemented
No `layer3c/3d/3_5` modules. 3B already auto-emits HITL items but **nothing gates on them** (CLAUDE.md lists 3.5 as a hard pre-plan-gen gate). This is **stop-and-ask trigger #4** + a spec-first multi-node build (per-node specs to the 14-section depth standard). The deferred "explicit-3D-revise eviction trigger" (CARRY_FORWARD) is also unwired. Biggest of the four — its own arc.

### 6.4 (#5) L3B §H.2 deployed-shape gap
`layer3b/cached_wrapper.py:155-158` accepts `goal_outcome` / `first_time_at_distance` / `previous_attempts` / `time_goal` / `race_pack_weight_kg` / `race_terrain` / `race_duration_hr` as None-tolerant kwargs that **don't exist on the deployed `RaceEventPayload`/`Layer1EventGoal`**; `goal_outcome` is band-aided to `"Finish"` (the #178 fix). So the `first_time_competitive_goal` / `dnf_recurrence_risk` HITL auto-emits are **unreachable** (silently degraded), and the planned L3B-P-3 flip (`Layer3BEvidenceBasisWarning` → hard `Layer3BOutputError("evidence_basis_mode_mismatch")`) is a latent new failure path. Cross-layer (`RaceEventPayload` schema) + coupled to the §H.2/§J/§I.1 form-refresh — its own slice.

### 6.5 Operating notes (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Fix = retry-on-missing-`sessions` (match the parse-fail path) + instrument | Andy ("Retry + instrument") | Uses the 2 retries that were already available + wasted; re-prompts the model with the miss; worst case degrades to the same terminal error → no regression. No prompt change, no cross-layer change. |
| 2 | Instrument = log the emitted `tool_args` keys at per_phase (not `stop_reason`) | Claude | `stop_reason` is consumed inside `invoke_tool_call` and not surfaced when a tool block IS returned; the keys tell us whether the dict was empty, partial, or wrong-keyed — the actionable signal at this layer. Surfacing `stop_reason` would touch the shared path (Andy's option B, not picked). |
| 3 | Fold in the over-emit clamp (#2) as a pure helper | Andy (scope select) + Claude | Same code locus + same recurring class; extracting `_clamp_sessions_over_emit` matches the 3A/3B `_clamp_*` precedent and is unit-testable without the orchestrator validator. |
| 4 | Defer #1/#4/#5 to their own slices (don't cram into this PR) | Claude→Andy | 5-file ceiling + spec-first; #4 is stop-and-ask #4 (HITL), #1 has an open routing decision (C3), #5 is a cross-layer schema change. Quality degrades past ~5 substantive files. Sequencing in §6. |

## 8. Session-end verification (Rule #10)

| Check | File:anchor | Method | Result |
|---|---|---|---|
| `_MAX_SESSIONS_PER_PHASE = 56` defined | `layer4/per_phase.py` near `DEFAULT_EXTENDED_THINKING_BUDGET` | grep | ✅ |
| `tool_schema = build_record_phase_sessions_tool(_MAX_SESSIONS_PER_PHASE)` | `layer4/per_phase.py` (in `synthesize_phase`) | grep | ✅ |
| `_clamp_sessions_over_emit` defined + called after the missing-`sessions` guard | `layer4/per_phase.py` | grep | ✅ |
| missing-`sessions` block retries (records `RuleFailure` + `continue`; raises only at `current_pass >= capped_retries`) | `layer4/per_phase.py` (synthesis loop) | read | ✅ |
| `Layer4OutputError` imported in the test | `tests/test_layer4_plan_create.py` | grep | ✅ |
| `TestMissingSessionsRetry` (3) + `TestSessionsOverEmitClamp` (2) green | `tests/test_layer4_plan_create.py` | pytest | ✅ |
| Full suite `pytest tests/` → 1729 passed / 16 skipped | — | fresh `/tmp/venv` | ✅ |
| `CURRENT_STATE.md` last-shipped = this handoff; #181 demoted to predecessor | `CURRENT_STATE.md` | read | ✅ |
| `CARRY_FORWARD.md` walk count +1; new shipped-item entry + deferred #1/#4/#5 | `CARRY_FORWARD.md` | read | ✅ |

## 9. Files shipped this session

**Substantive (code, 1 file):**
1. `layer4/per_phase.py`

**Tests:**
2. `tests/test_layer4_plan_create.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
