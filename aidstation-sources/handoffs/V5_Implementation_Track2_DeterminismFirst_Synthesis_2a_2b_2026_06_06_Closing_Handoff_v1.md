# V5 Implementation — Track 2 Determinism-First Layer 4 Synthesis: spec APPROVED + slices 2a + 2b shipped

**Date:** 2026-06-06
**Branch:** `claude/stoic-darwin-f3h6w`
**PR:** #433 — **CI green; squash-merged to `main`.**
**Issues:** Track 2 (#429) of the 3-track redesign epic #427. Spec `Layer4_DeterminismFirst_Synthesis_Design_v1.md` is **APPROVED**. Slices 2a (tool-schema enum) and 2b (session-count grid + intensity split + prompt rewrite + volume_band demotion) shipped. Slices 2c + 2d still owed (see §5).

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch 403s (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. Untruncated runtime logs: Vercel dashboard (team `team_rkZGxltBw2ykWtrIPCYy16JZ`, project `prj_MRcYT23wGVekzavrrfWYUOTYlUPO`); the runtime-log MCP truncates the message column (Rule #14).

---

## 1. What this session was

Andy named Track 2 as the next move after Track 1 shipped. This session spec'd it (Andy red-penned in two rounds → APPROVED), then implemented slices 2a + 2b end-to-end inside PR #433. Two stop-and-ask gates resolved during execution (§3). All work green on the in-container test suite (no Neon egress needed for 2a/2b — these are pure-function + prompt changes).

## 2. Shipped

### 2.1 — Spec: `Layer4_DeterminismFirst_Synthesis_Design_v1.md` (APPROVED)

Status block flipped DRAFT → APPROVED at session close. Spec encodes the 4-slice arc (2a → 2d):

- **§2 locked decisions** — Andy 2026-06-06: D1 tool-schema enum; D2 session-count grid with maintenance-cadence rule for sub-0.5-sessions/wk disciplines; D2-AR race-sim long days + brick pairing (nav-modifier + skill-cap-bias deferred); D3 polarized intensity (90/10 → 80/20 → 70/30 → 90/10 per Seiler); D4 rest detection (not placement — LLM keeps placement freedom, deterministic post-check warns on insufficient rest); D5/D6 Andy's reframe of locale assignment (LLM picks ideal set locale-agnostic → deterministic majority-fit locale → deterministic pattern-match substitution → Tier-3 proxy → small dedicated LLM call as last-resort); D7 `rx_engine` post-hoc wiring (deterministic RPE-only template for first-exposure — no LLM, no guessed weight); D8 per-rule validator demotion table; D9/D10 four-slice PR split.
- **§4 D1 expanded** — Andy 2026-06-06 picked option A (enum all four tool schemas: `record_phase_sessions`, `record_refresh_sessions`, `record_single_session`, `record_race_week_brief`) over option B (per_phase only + Rule 6a demoted-not-deleted). Keeps "structurally impossible" guarantee honest across every synth path.
- **§5.5.5** small-call LLM substitution as the locale-assigner's last-resort fallback — tight prompt, Haiku-class, cache key `(exercise_id, locale_id, excluded_ids_hash)`.
- **§7 first-exposure** = deterministic RPE-only template keyed off exercise category, NOT LLM text (Andy's correction).
- **§11 travel/hotel** = `hotel_gym` shared profile default fallback when athlete is out of cluster without a defined locale.

### 2.2 — Slice 2a: tool-schema enum on `exercise_id` (4 paths) + Rule 6a retired (commit `e9ad368`)

Implements D1. The four LLM tool schemas that emit `strength_exercises.exercise_id` gain a `feasible_pool_ids` enum constraint that bounds the field to the cluster-union of `Layer2C.exercises_resolved` minus `Layer2D.excluded_exercises`. Out-of-pool picks are now structurally impossible at the SDK boundary across **all** four synthesis paths.

- **`layer4/per_phase.py`** — NEW `compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)` canonical helper (sorted+deduped for deterministic enum ordering, cache-key stability). `_session_schema` + `build_record_phase_sessions_tool` accept `feasible_pool_ids: list[str] | None`; caller at `synthesize_phase` computes + passes (`feasible_pool_ids or None` to preserve free-string when pool empty). Warning log at >200 enum (2C/2D mis-filter signal; per-block scoping keeps real-world cases well under).
- **`layer4/plan_refresh.py`**, **`layer4/single_session.py`**, **`layer4/race_week_brief.py`** — same shape; each imports the canonical helper. single_session wraps single-locale `layer2c_payload_for_locale` as `{locale_id: l2c}`.
- **`layer4/validator.py`** — `_rule_equipment_unavailable` **deleted**; replaced with a retire-stub comment; removed from `_ALL_RULES`. Adjacent comments referencing "Rule 6a equipment_unavailable" updated to reference the Track 2 D1 structural enum.
- **`layer4/__init__.py`** — re-exports `compute_feasible_pool_ids`.
- **Tests:** `TestComputeFeasiblePoolIds` (4 tests, cluster-union + 2D-exclusion correctness); `test_feasible_pool_enum*` (3 tests on `build_record_phase_sessions_tool` covering enum present / empty / None). 3 deleted Rule 6a tests + adjacent stale comments updated. **Suite 2003 passed / 16 skipped.**

### 2.3 — Slice 2b: deterministic session-count grid + prompt rewrite + volume_band demotion

Three commits (one per substantive piece) so the diff reviews cleanly.

#### 2.3.1 `layer4/session_grid.py` NEW (commit `1bf07d8`)
Pure-function module implementing §5.1 + §5.2 + §5.3.
- `build_session_grid(layer2a, phase_structure, phase_name, week_in_phase, capacity_hours, *, race_format, race_duration_h) -> SessionGrid`
- Per-discipline counts: `phase_load × weekly_capacity × periodization_multiplier ÷ typical_session_hours`. `_DISCIPLINE_TYPICAL_SESSION_HOURS` per-discipline constants table (PGE coverage explicit, fallback 1.0h). v1.1 candidate: lift to a layer0 coach-config table.
- **Maintenance cadence (§2.2):** disciplines below 0.5 sessions/week rotate onto `ceil(1 / raw_count)` weeks (climbing at 3% of PGE = 1 session every 4 weeks, not weekly). Prevents over-allocation of small-share disciplines.
- **Polarized intensity (§5.3):** Base 90/10 → Build 80/20 → Peak 70/30 → Taper 90/10. No moderate (Seiler 2010). Strength sessions excluded (cardio-aerobic concept). Build/Peak floor 1 hard session when total ≥3.
- **Race-sim long day (§5.2):** `continuous_multi_day` race format → Peak (every week) + Taper-1 (60% of Peak). Duration `min(8h, race_duration / 8)`. Multi-discipline, weekend-anchored.
- **Tests:** `tests/test_layer4_session_grid.py` — 15 unit tests covering counts, maintenance cadence, polarized split, race-sim. **Suite 2018 passed.**

#### 2.3.2 `layer4/per_phase.py` prompt rewrite (commit `8e3cc33`, option A per Andy)
The load-bearing piece. The LLM's job shifts from "allocate the week" to "place + select content within the grid."

- **SYSTEM_PROMPT cut:** the "Phase intent" volume-band paragraph; the hardcoded strength dose ("Base/Build 2 sessions/week, Peak 1..."); the deload-shape paragraph (periodization grid handles it).
- **SYSTEM_PROMPT add:** "Session grid — deterministic counts + intensity mix" section explicitly declaring the grid authoritative. Calls out maintenance cadence + cardio-only intensity mix + race-sim slot semantics. Tells LLM to call out grid errors in `phase_synthesis_notes` rather than silently deviate.
- **`_format_session_grid()` NEW** — renders per-week `=== Session grid (deterministic — Track 2 §5.1/§5.2/§5.3) ===` block: per-discipline counts × typical minutes × target hours (with cadence_note when sub-threshold); polarized intensity mix at-the-week-level; race-sim long day when present.
- **`_format_phase_load_bands` DELETED** — orphaned by the rewrite (only call site was the user-prompt renderer it replaces).
- **`render_user_prompt`** swap: the old `Per-week volume targets per discipline` + `Intended intensity distribution` lines REMOVED; the new `=== Session grid ===` block REPLACES both. Race_event_payload threaded through for the race-sim slot.
- **Tests:** `TestSessionGridPromptRewrite` (6 tests) — grid block appears, per-discipline counts render, polarized intensity mix renders, old allocation framing removed, race-sim absent for single-day, SYSTEM_PROMPT no longer carries hardcoded dose.

#### 2.3.3 `layer4/validator.py` volume_band demotion (commit `8e3cc33`)
`_rule_volume_band` fully demotes to warning across both band widths (was blocker at ±20%, warning at ±10%). The deterministic session_grid is the new allocation gate; the validator's role here shifts from gating to advisory drift detection. `_rule_intensity_dist` already emitted warning — no change needed. 8 existing volume_band tests updated to expect warning (per spec §8 Rule 1).

**Final suite: 2024 passed / 16 skipped.**

## 3. Stop-and-asks this session

1. **D2 maintenance cadence vs over-allocation** (Andy 2026-06-06): the original D2 grid would round small-share disciplines (climbing at 3% of PGE) up to 1 session/week. Andy flagged this overtrains tiny race-share disciplines. Resolution: `_MAINTENANCE_CADENCE_THRESHOLD = 0.5` — sub-threshold disciplines rotate onto multi-week cadence (`ceil(1/raw_count)` weeks) instead of weekly.
2. **D7 first-exposure: LLM text vs RPE-only template** (Andy 2026-06-06): original spec kept LLM text when `current_rx` returned None. Andy's correction: just state RPE since the weight is genuinely unknown. Resolution: deterministic RPE-only template keyed off exercise category (`compound_barbell` / `compound_dumbbell` / `accessory_*` / `bodyweight`) — no LLM, no guessed weight, athlete sets baseline via calibration set.
3. **D4 rest = detection vs placement** (Andy 2026-06-06): original spec had `rest_days() -> set[Weekday]` placing rest deterministically. Andy: don't enforce; warn when insufficient. Resolution: `expected_rest_count` (advisory) + `detect_insufficient_rest` (deterministic post-check emitting `insufficient_rest` coaching flag).
4. **Slice 2a scope expansion to all 4 tool schemas** (Andy 2026-06-06): the original spec §10 listed per_phase + validator only. Discovered 3 other tool schemas also emit `exercise_id`; deleting Rule 6a without enum-bounding those would create a feasibility-gating hole. Andy picked option A (all 4 paths) over option B (per_phase only + Rule 6a demoted-not-deleted).
5. **Slice 2b prompt rewrite approach** (Andy 2026-06-06, CLAUDE.md trigger #1): presented three options (A tight rewrite / B additive / C tight + override language). Andy picked A. Cut the now-stale allocation/dose/deload text; added explicit "grid is authoritative" framing.

## 4. Owed (Andy's hands)

> Slice 2a + 2b are pure-function + prompt changes — no schema DDL, no Neon egress needed. Owed = the live proof.

1. **Re-run a cold PGE plan.** The same win condition Track 1 owed PLUS Track 2's:
   - **From Track 1:** no `equipment_unavailable` blockers (was structurally impossible after slice 2a; this is also the visible Track 1 proof on the diag endpoint's `effective_pool` showing canonical names).
   - **From slice 2a:** the validator's `validator_failures_by_rule` distribution should show **zero** `equipment_unavailable_*` rows (the rule no longer exists).
   - **From slice 2b:** the synthesizer prompt should consume the new `=== Session grid ===` block — pulled diag JSON should show per-discipline session counts matching the grid output (e.g. for PGE Build:w1 with capacity 12h, climbing should appear in 1 week then skip 3 weeks per maintenance cadence). `volume_band` failures (if any) should now be `severity=warning`, not blocker.
   - **Smell test:** the resulting plan should look "polarized" — most cardio sessions easy, a small number hard, no slog of moderate Z3 work. Race-sim long day should appear in Peak (1 × 7h for PGE if `estimated_duration_hr` set to ~56h).
2. **(Optional)** poke the per-discipline `_DISCIPLINE_TYPICAL_SESSION_HOURS` constants in `layer4/session_grid.py` if any allocation looks obviously wrong for a PGE discipline — these are coach-estimate defaults, easy to tune in a follow-up session.

## 5. Next move

- **Slice 2c (next slice of this Track 2):** deterministic locale assignment + substitution pipeline (`layer4/locale_assign.py`) + rest detection (`expected_rest_count` + `detect_insufficient_rest` extensions to `session_grid.py`). Per spec §5.5 + §5.4. Five substantive files: `session_grid.py`, `locale_assign.py` (NEW), `plan_create.py` + `plan_refresh.py` (call sites), `validator.py` (demote Rules 3 + 11 to warning).
- **Slice 2d (final slice of Track 2):** `rx_engine` post-hoc wiring (`layer4/rx_wire.py` NEW; first-exposure deterministic RPE template) + the remaining §8 validator demotions. Per spec §7. Track 3 dependency note: `rx_engine` reads `public.exercise_inventory`; Track 3 moves to `layer0.*`. Until Track 3 ships, rx lookups limited to the public catalog subset — layer0-only exercises fall through to first-exposure (acceptable v1 behavior).
- **Track 3 (#430) — D-52 catalog migration** (parallel/after Track 2): retire `public.exercise_inventory`/`exercise_equipment`/`equipment_items` → `layer0.*`; restores the v1 references/purchases surfaces degraded in Track 1.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (Track 2 in-flight items updated this session)
4. This handoff (diagnostic token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Spec APPROVED, 4-slice plan locked | `aidstation-sources/Layer4_DeterminismFirst_Synthesis_Design_v1.md` | `grep -n "Status:.*APPROVED" Layer4_DeterminismFirst_Synthesis_Design_v1.md` |
| Canonical feasible-pool helper + 4-path enum | `layer4/per_phase.py`, `plan_refresh.py`, `single_session.py`, `race_week_brief.py` | `grep -rn "compute_feasible_pool_ids\|feasible_pool_ids" layer4/` |
| Rule 6a retired + retire-stub | `layer4/validator.py` | `grep -n "Rule 6a retired\|_rule_equipment_unavailable" layer4/validator.py` (function should be GONE; retire-stub comment present) |
| Session grid module | `layer4/session_grid.py` | `grep -n "def build_session_grid\|_MAINTENANCE_CADENCE_THRESHOLD\|_PHASE_INTENSITY_SPLIT\|_RACE_SIM_FRACTION_OF_RACE" layer4/session_grid.py` |
| Prompt rewrite — grid is authoritative | `layer4/per_phase.py` | `grep -n "Session grid — deterministic\|=== Session grid\|def _format_session_grid" layer4/per_phase.py` |
| Old phase_load_bands renderer deleted | `layer4/per_phase.py` | `grep -n "_format_phase_load_bands" layer4/per_phase.py` (should return 0 matches) |
| volume_band demoted to warning | `layer4/validator.py` | `grep -n "Track 2 slice 2b: demoted to warning" layer4/validator.py` |
| Test coverage | `tests/test_layer4_session_grid.py`, `tests/test_layer4_plan_create.py` (`TestSessionGridPromptRewrite` + `TestComputeFeasiblePoolIds`) | full suite 2024 passed / 16 skipped |
