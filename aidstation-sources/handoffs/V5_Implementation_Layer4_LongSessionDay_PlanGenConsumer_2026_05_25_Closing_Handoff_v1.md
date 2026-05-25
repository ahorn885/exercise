# Layer 4 — plan-gen long-session-day consumer (longest enabled window) — Closing Handoff

**Session:** Form-feedback follow-on. Andy picked the **plan-gen long-session placement** open move from the FormRefresh Slice C handoff §6.2 ("Slice C made the long session 'the longest enabled window,' but no Layer 4 plan-gen node *consumes* that yet"). Designed + ratified at an AskUserQuestion gate (Trigger #1 — prompt-body modification), then implemented.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_FormRefresh_C_ScheduleInference_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/v5-form-refresh-schedule-handoff-rjeik`
**Status:** Implementation complete on-branch; **PR #163 merged**. 4 substantive files (3 code + 1 spec) + 1 test suite. Full container suite green (1786 passed / 16 skipped). **No deploy owed** (prompt-body + render change only; no schema change). The A1/A2/Slice-C owed Neon deploys are unchanged by this slice.

---

## 1. Session-start verification (Rule #9)

Picked up mid-session at Andy's direct pick (no `verify-handoff.sh` anchor sweep this turn). Reconciled the claimed Slice C state against on-disk reality before designing, since this slice builds directly on Slice C's derived-semantic claim:

- Confirmed Slice C's contract is on-disk: `Layer1_Spec.md` line 119 explicitly states the weekly long session + rest days are **derived by the consumer (plan-gen), not denormalized scalars**. `layer1/builder.py:411` carries the same semantic in a comment. So the "consumer" this slice adds is exactly what Slice C deferred.
- Confirmed the **gap**: `per_phase.py` was the *only* plan-gen node rendering `daily_availability_windows`, and it did so as a raw `f"Daily availability windows: {windows} ..."` dump (old line ~872) with only the hard `daily_window_fit` constraint — it never named the longest enabled window as the long-session day, so the §146 `long_slow_distance` cornerstone wasn't steered there. The refresh tiers (`plan_refresh_t2`/`_t3`) referenced "long-session anchor placement" in their SYSTEM_PROMPTs but rendered **no** window data at all (only `experience_level` / `coaching_voice` off `layer1_payload`).
- Confirmed no existing validator rule ties the LSD to the longest window (`validator.py` `_rule_daily_window_fit` only checks total session minutes ≤ window minutes), so this is a pure soft-steer, not a missing guardrail.

Test-environment: fresh web container, deps not pre-installed; `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`. Suite collects + runs clean.

---

## 2. Session narrative

Andy: "let's work. what are the next few items not including the work I need to do locally" → I listed the three non-local open moves from Slice C §6.2 (navigation_required → race_events; spec narrative sweep; plan-gen long-session placement). Andy picked **"3"** (plan-gen long-session placement) — the one I'd flagged as possibly premature.

Per Trigger #1 (prompt-body modification) I researched + designed before building. Traced the full surface: `per_phase.py` is the sole window-rendering node (Pattern A — plan_create + T3 cross-phase); the refresh tiers reference an anchor they have no data to place; `layer1_payload` is `.model_dump()`'d so `daily_availability_windows` is a **list of dicts** (keys: `day_of_week` / `enabled` / `window_start` / `window_duration` / `second_window_*` / `doubles_feasible`). Presented the design + two scope forks at an AskUserQuestion gate.

**Andy's gate picks (§7):** (1) **soft prompt-steer only** — no validator rule; (2) **per_phase + refresh tiers T2/T3** (the wider scope, closing the latent refresh-tier inconsistency). Implemented, tested green, opened draft PR #163, CI (Vercel) green, then un-drafted + merged at Andy's instruction.

---

## 3. File-by-file edits

### Substantive code (3)

#### 3.1 `layer4/per_phase.py`
- **NEW `_format_daily_windows_schedule(layer1_payload: dict) -> list[str]`** (after `_format_training_substitution_per_phase`, ~line 702). Renders the `=== Schedule ===` section: `available_days_per_week` line + one line per day (`- {dow}: available, {dur} min [(+ {sec} min second window)]` or `- {dow}: rest (unavailable)`), marks the longest enabled window inline (`  ← longest enabled window`), surfaces `doubles_feasible` once, then a **Long-session day = {dow} ({dur} min, the longest enabled window)** line steering the primary discipline's weekly `long_slow_distance` cornerstone there (secondary-discipline LSDs to their own longest available day). Tie among equal-duration enabled windows → **earliest listed day** (strict `>` keeps the first max). Graceful fallbacks: empty/missing windows → "(No per-day availability windows on file.)"; all-disabled → "No enabled windows — the whole period is rest".
- `render_user_prompt`: replaced the inline 11-line raw `{windows}` dump (old `=== Schedule ===` block) with `parts.extend(_format_daily_windows_schedule(layer1_payload))` (now ~line 938).
- `SYSTEM_PROMPT` §162 "Schedule respect": appended the long-session-day policy (longest enabled window = long-session capacity since Slice C retired the standalone input; anchor primary-discipline LSD there; the `=== Schedule ===` block names the computed day).

#### 3.2 `layer4/plan_refresh_t2.py`
- Import: `_format_daily_windows_schedule` added alongside `_format_training_substitution_per_phase` from `layer4.per_phase`.
- `render_user_prompt`: inserted a `=== Schedule ===` section (`parts.extend(_format_daily_windows_schedule(layer1_payload))`, ~line 183) right after the Athlete-profile block — T2 previously rendered no window data.
- `SYSTEM_PROMPT` WEEKLY-AGGREGATE GUARDRAILS LSD bullet: appended the long-session-day anchoring note (primary-discipline LSD on the longest enabled window named in `=== Schedule ===`; secondary LSDs to their own longest day).

#### 3.3 `layer4/plan_refresh_t3.py`
- Same three edits as T2 (import; `=== Schedule ===` section ~line 224 after the post-cascade Athlete-profile block; the per-week LSD bullet note).

### Spec (1)

#### 3.4 `aidstation-sources/Layer4_Spec.md`
- §114 `layer1_payload` row: extended the §K description to record that the **long-session day is derived as the longest enabled window** (FormRefresh Slice C), anchoring the primary discipline's weekly `long_slow_distance` cornerstone, rendered by `per_phase._format_daily_windows_schedule` and shared into plan_refresh T2/T3.

### Test (1)

#### 3.5 `tests/test_layer4_plan_create.py`
- **NEW `class TestDailyWindowsSchedule`** (after `TestPerPhasePromptRendering`, ~line 1207) — 5 cases on the helper: longest-window detection + naming; tie → earliest listed day; all-disabled → no long-session day; missing-windows graceful; second-window + doubles surface. Uses a `_w(...)` dict-builder mirroring the `.model_dump()` shape.

### NOT touched (decision #4 — design-wave precedent)
- `aidstation-sources/prompts/Layer4_PerPhase_v2.md`, `Layer4_RefreshT2_v1.md` — these explicitly defer the **verbatim** coaching policy + §6 user-prompt template to `layer4/per_phase.py:SYSTEM_PROMPT`, and document only **contract** (input/output schema) amendments. This change is additive prompt guidance over an input (`daily_availability_windows`) already in the §3 contract — not a schema change. Left as-is, matching the Slice C decision-#6 precedent (canonical text lives in code + `Layer4_Spec`). If Andy wants a one-line amendment banner in those docs, it's a cheap follow-up.

---

## 4. Code / tests

Container suite: **1786 passed / 16 skipped** (`/tmp/venv`). **Net test delta: +5** (the new `TestDailyWindowsSchedule` cases; nothing removed). `test_layer4_plan_create.py` + `test_layer4_plan_refresh.py` together: 133 passed. All suites collect with no errors. (Absolute count 1786 vs Slice C's 1641 reflects the per-env pydantic/flask/pytest difference noted in `CURRENT_STATE.md` §Tests, not lost coverage — measured in the same fresh-venv shape, +5 over this env's baseline.)

Eyeballed the rendered `=== Schedule ===` block against a realistic 7-day Andy-shaped window set (Sat 600 min → correctly named the long-session day). No LLM run in-container — the actual adherence check (does the synthesizer place the LSD on the named day) is an owed manual §5.0 step.

---

## 5. Manual §5.0 verification steps (owed — Andy's hands)

Appended to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" as the **Layer4 long-session-day** entry:
1. Run a `plan_create` (or a T3 cross-phase refresh) with `ANTHROPIC_API_KEY` set against an athlete whose longest enabled window is a specific day (e.g., Sat 600 min). Confirm the synthesizer places the primary discipline's `long_slow_distance` session on that day and respects disabled days as rest.
2. Run a T2 (7-day) refresh and confirm the new `=== Schedule ===` block renders + the LSD lands on the long-session day.

No migration, no deploy owed for this slice.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Run the owed Neon deploys** (still Andy's hands; unchanged by this slice): the public-schema `python init_db.py` (A1 race_events remap + A2 `aid_stations` drop + Slice-C §G column drops + `daily_availability_windows` 720 CHECK bump — one idempotent run) **plus** the layer0 `etl/sources/run_owed_layer0_migrations.sql` runner (PR #156 `primary_movement` HARD Layer-2A prereq). Then the accumulated manual §5.0 UI/LLM eyeballs.

### 6.2 Open pivots
- **`navigation_required` → `race_events` column** — promote the unwired Layer 3B input (home for the nav/weather contingency anchors removed in A1). Cross-layer (Trigger #3); needs plan-mode design. *(Note: `validator.py` `_CONTINGENCY_ANCHORS_PER_FORMAT` comment already flags a "future slice keyed on discipline / exposed-terrain-driven anchor" — related territory.)*
- **Spec narrative sweep** — per-layer specs still cite pre-R6 discipline ids in prose; design-wave docs may carry stale §G claims. Doc-only; no gate.
- **Prompt-doc amendment notes (optional)** — if the design-wave prompt-body docs (`Layer4_PerPhase_v2.md`, `Layer4_RefreshT2_v1.md`) should reflect this slice's `=== Schedule ===` enrichment, add a one-line amendment (see §3 NOT-touched rationale).
- **Manual §5.0 real-LLM walk** — accumulated scenarios in `CARRY_FORWARD.md`.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (read first).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.
6. **Test env:** deps not pre-installed in fresh web containers — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Soft prompt-steer only** — no validator rule | Andy at gate | The existing `daily_window_fit` rule already hard-blocks impossible placements; Slice C deliberately demoted the long session from an explicit picker to a soft signal, so a hard validator rule would over-correct + risk false positives (doubles, multi-discipline contention). |
| 2 | **Scope = per_phase + refresh T2/T3** (the wider fork) | Andy at gate | The refresh tiers already *referenced* "long-session anchor placement" but rendered no window data — a latent inconsistency worth closing in the same slice. |
| 3 | **Tie among equal-duration enabled windows → earliest listed day** | this agent (within scope) | Deterministic, matches the order the LLM sees; avoids an ambiguous "the longest window" when two days match. |
| 4 | **Leave design-wave prompt-body docs untouched** | this agent | They defer verbatim policy to `per_phase.py:SYSTEM_PROMPT` and document only contract amendments; this is additive guidance over an in-contract input. Matches Slice C decision-#6. Canonical text = code + `Layer4_Spec` §114. |
| 5 | **Multi-discipline split**: primary-discipline LSD on the long-session day; secondary-discipline LSDs on their own longest available day | this agent (within scope) | Only one long-session day exists but §146 wants one LSD per (week, discipline); without the split the instruction self-contradicts. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -n "def _format_daily_windows_schedule" layer4/per_phase.py` → defined ~702 | ✅ |
| `per_phase.render_user_prompt` calls `_format_daily_windows_schedule(layer1_payload)` (raw `{windows}` dump gone) | ✅ (~938) |
| `per_phase.py` SYSTEM_PROMPT §162 carries "long-session day" policy | ✅ (2 hits) |
| `plan_refresh_t2.py` imports + calls helper (~183) + LSD-bullet note | ✅ |
| `plan_refresh_t3.py` imports + calls helper (~224) + LSD-bullet note | ✅ |
| `Layer4_Spec.md` §114 carries "long-session day is derived as the longest enabled window" | ✅ (1 hit) |
| `tests/test_layer4_plan_create.py` has `class TestDailyWindowsSchedule` (5 cases) | ✅ (~1207) |
| `TestDailyWindowsSchedule` green | ✅ 5 passed |
| `test_layer4_plan_create.py` + `test_layer4_plan_refresh.py` green | ✅ 133 passed |
| Full suite | ✅ 1786 passed / 16 skipped (`/tmp/venv`) |
| Rendered `=== Schedule ===` eyeball (Sat 600 → long-session day) | ✅ |
| Working tree: only the intended files | ✅ git status |
| PR #163 | ✅ merged to `main` |

---

## 9. Files shipped this session

**Substantive code (3):** `layer4/per_phase.py`, `layer4/plan_refresh_t2.py`, `layer4/plan_refresh_t3.py`.
**Spec (1):** `aidstation-sources/Layer4_Spec.md` (§114, in-place).
**Tests (1):** `tests/test_layer4_plan_create.py` (`TestDailyWindowsSchedule`).
**Bookkeeping:** this handoff; `CURRENT_STATE.md` pointer + open-moves; `CARRY_FORWARD.md` §5.0 entry.

---

## 10. Carry-forward updates

- New Manual §5.0 entry (Layer4 long-session-day LLM-adherence + T2 schedule render) appended to `CARRY_FORWARD.md`.
- The numbered form-feedback batch (items 1–6) remains fully closed; this slice is a Slice-C *consumer* follow-on, not a new batch item.
- The owed Neon deploys (A1/A2/Slice-C public schema + layer0 runner) are **unchanged** by this slice — no new deploy debt.

---

**End of handoff.**
