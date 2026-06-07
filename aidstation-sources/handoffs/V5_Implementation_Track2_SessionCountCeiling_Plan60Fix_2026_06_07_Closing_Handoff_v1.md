# V5 Implementation — Track 2 follow-up: session-count ceiling (slice 2b.2a) — plan #60 stall fixed

**Date:** 2026-06-07
**Branch:** `claude/plan-60-monitoring-kCS2m`
**PR:** #465 (spec v2 + slice 2b.2a)
**Issues:** Track 2 (#429) of epic #427. Spec `Layer4_DeterminismFirst_Synthesis_Design_v2.md` (bumped from v1, Rule #12). New backlog issue **#469** (lb/kg unit-preference toggle).

---

## ⚡ Diagnostic token (read first — every monitoring session)

```
DIAG_TOKEN = 0dKHoR2Ub5laemc-_Gmu7nHjErZzxyIevy8plBUAyWc
```
`GET https://aidstation-pro.vercel.app/admin/plan/<id>/diag?token=…` — WebFetch/curl 403 (Vercel deployment protection); fetch via the **Vercel MCP `web_fetch_vercel_url`** tool. The token diag carries the control row + block-level `synthesis_metadata` (cap_hit / latency / tokens / retries) + the stall traceback — **NOT** session bodies / per-session metadata / per-rule validator severities. Those need `/admin/plan/<id>/inspect` (admin login; no token bypass).

---

## 1. What this session was

Monitored the cold PGE plan **#60**. It **failed** — D-77 wall-clock stall backstop fired after only Build:w1 cached. Root-caused (with Andy pasting the Layer 4 log line, Rule #14) to the **session-count grid**: it summed per-discipline counts with no global ceiling and no available-days awareness, prescribing **14 sessions** for Andy's 6-training-day week (hard max `2 × 6 = 12`). Build:w2 was unschedulable under the `two_per_day` payload invariant → every synth attempt raised a `Layer4Payload` ValidationError at construction (`"2026-06-19: max 2 sessions per day (got 3)"`) → `synthesis_budget_exhausted` → no progress → stall → plan `failed`. (Build:w1 only "passed" by spilling onto the rest day — a now-demoted `schedule_violation` warning — so the plan was broken either way.)

Designed the fix with Andy, wrote spec v2, and shipped slice 2b.2a. Not the validator-retry loop Track 2 retired — an upstream feasibility gap in slice 2b's grid.

(Also surfaced, unrelated: `athlete_context.weight=161.0kg` in the 3A context — a lb value in the kg-labeled `body_weight_kg` profile field. Andy confirmed the mis-entry. Filed as #469; NOT the #60 cause.)

## 2. Shipped (slice 2b.2a — PR #465)

### 2.1 — `layer4/session_grid.py` — the ceiling (§5.1.1, D11)

- `resolve_available_days(layer1_payload)` — `available_days_per_week` → else enabled-`daily_availability_windows` count → else **7** (D-7: assume all days/hours).
- `phase_session_ceiling(phase, available_days, two_a_day_preference=None, peak_sessions_max=None)` — Peak ceiling (`peak_sessions_max` default **10**, else density × days, else default) scaled per phase, hard-clamped to `2 × available_days`.
  - Density map: never 1.0 / occasionally 1.5 / regularly 1.85.
  - Phase scales (near-flat, sport-science D-8): Base 0.90 / Build 1.00 / Peak 1.00 / Taper 0.85.
- `apply_session_ceiling(allocations, phase, available_days, …)` — sheds lowest-`load_weight` first (allocations are pre-sorted desc): **trim multi-session disciplines toward 1 before dropping any to 0**; dropped ones get a `cadence_note` and rotate back on lighter weeks. Identity-preserving when nothing to shed. **Volume preserved** — `target_hours_this_week` untouched (fewer, longer sessions, Andy's call).
- `build_session_grid` gained `available_days` / `two_a_day_preference` / `peak_sessions_max` (keyword-only); applies the ceiling after the per-discipline allocation, before the cardio/intensity count. **No ceiling when `available_days is None`** (back-compat for bare unit callers).
- **No HITL fail-path.** The spec'd `discipline_frequency_infeasible` raise was dropped — there's no HITL in v1, so the deterministic shed/rotation always converges instead of failing (Andy 2026-06-06).

### 2.2 — `layer4/per_phase.py` — call-site wiring

At the `build_session_grid` call site (the grid-rendering prompt helper), resolve `available_days = resolve_available_days(layer1_payload)` + read `two_a_day_preference` / `peak_sessions_max` from the payload (both default until 2b.2b) and pass them through.

### 2.3 — §5.4 rest-detection removed (Andy: "the athlete owns their rest days")

- `session_grid.py`: deleted `expected_rest_count`, `detect_insufficient_rest`, `InsufficientRestWarning`, `_PHASE_EXPECTED_REST_DAYS`.
- `validator.py`: deleted `_append_insufficient_rest_warnings` + its call in `_rule_rest_spacing` (the **consecutive-hard recovery-spacing** advisory in Rule 3 stays — that's not a rest-day-count override). Fixed two stale comments referencing the removed helpers.
- `__init__.py`: re-exports swapped (rest symbols out; `apply_session_ceiling` / `phase_session_ceiling` / `resolve_available_days` in).

### 2.4 — Tests

`tests/test_layer4_session_grid.py`: removed `TestExpectedRestCount` + `TestDetectInsufficientRest`; added `TestPhaseSessionCeiling` / `TestApplySessionCeiling` / `TestResolveAvailableDays` / `TestBuildGridCeilingIntegration`. `tests/test_layer4_validator.py`: docstring fix. **Full suite 2106 passed / 16 skipped, 0 failed.**

### 2.5 — Spec v2

`Layer4_DeterminismFirst_Synthesis_Design_v2.md` (bumped from v1 per Rule #12; v1 retained). New §2 item 10 (D11), §5.1.1 (the design + numbers + citations), §5.4 correction note, §10 slice 2b.2 plan (2b.2a SHIPPED / 2b.2b owed), §12 D-7/D-8 resolved, §13 win condition.

## 3. Stop-and-asks this session

- **Session-count philosophy + the two athlete knobs** (Trigger #5) — Andy chose: `peak_sessions_max` default 10, categorical `two_a_day_preference` as the friendly primary control, fewer/longer (preserve volume), all-days fallback.
- **§5.4 rest removal** — confirmed by Andy before the code change landed (it touched shipped 2c).
- **D-8 numbers** — researched sport-science (taper holds frequency; frequency stable across phases) → revised phase scales; reported with citations before locking.

## 4. Owed

1. **The cold PGE plan #60 re-run is Andy's-hands** (needs the merge → prod deploy, then trigger a cold plan; generation is behind the login wall, I can't trigger it). Win condition (spec §13): every week ≤ phase ceiling (Andy: Base/Build/Peak ≈ 9–10, Taper ≈ 8–9, cap 12), **no day > 2 sessions, no `two_per_day` ValidationError, the athlete's disabled days carry zero sessions**, and the Build:w2 stall does not recur. I can monitor the diag once it's running.
2. **Slice 2b.2b** — the athlete-facing fields: `athlete_profile.two_a_day_preference` (`never`/`occasionally`/`regularly`) + `peak_sessions_max INT` via `_PG_MIGRATIONS` (**Neon migration owed-Andy's-hands**); `layer4/context.py` Layer 1 §K schema/payload; onboarding + `routes/profile.py` UI (the categorical primary + advanced number; reject `peak_sessions_max > 2 × available_days_per_week`). Until then the grid uses the spec defaults (which is what unblocks the re-run).
3. **#469 — lb/kg unit-preference toggle.** Bigger feature (onboarding/profile + training-log + body-metrics + Layer 1 + rx display). Includes reconciling user 1's `body_weight_kg=161` mis-entry. Own spec + slice.
4. **Carried from Track 2 close:** 2c.2 cardio routing + layer0 vocab adds (TRN-017 / TRN-007 rename) + snow-sports semantics + Track 3 (#430) catalog migration. See CARRY_FORWARD.

## 5. Next move

Tier order (CLAUDE.md 4-tier): the #60 re-run (go-live blocker proof) is the gating item — merge PR #465, Andy re-runs, I monitor. Then 2b.2b (finish the partial feature → surface the athlete control). Then #469 / 2c.2 / Track 3.

### 5.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (2b.2b, #469, 2c.2, Track 3)
4. This handoff (diag token in the ⚡ callout)
5. `./scripts/verify-handoff.sh` — automated anchor sweep

## 6. §8 anchor table (Rule #10 — file + anchor + check)

| Claim | File | Anchor / check |
|---|---|---|
| Ceiling functions added | `layer4/session_grid.py` | `grep -n "def apply_session_ceiling\|def phase_session_ceiling\|def resolve_available_days\|_PHASE_SESSION_SCALE\|_TWO_A_DAY_DENSITY" layer4/session_grid.py` |
| Rest detection removed | `layer4/session_grid.py` | `grep -n "detect_insufficient_rest\|expected_rest_count\|InsufficientRestWarning" layer4/session_grid.py` → **0 hits** |
| Call-site wiring | `layer4/per_phase.py` | `grep -n "resolve_available_days\|available_days=available_days" layer4/per_phase.py` |
| Validator rest warning removed | `layer4/validator.py` | `grep -n "_append_insufficient_rest_warnings\|insufficient_rest" layer4/validator.py` → **0 hits** |
| `__init__` re-exports | `layer4/__init__.py` | `grep -n "apply_session_ceiling\|phase_session_ceiling\|resolve_available_days" layer4/__init__.py` |
| Spec v2 ceiling section | `aidstation-sources/Layer4_DeterminismFirst_Synthesis_Design_v2.md` | `grep -n "5.1.1 Session-count ceiling\|2b.2a SHIPPED" Layer4_DeterminismFirst_Synthesis_Design_v2.md` |
| Test coverage | `tests/test_layer4_session_grid.py` | `TestPhaseSessionCeiling` / `TestApplySessionCeiling`; full suite **2106 passed / 16 skipped** |

## 7. Mechanically-applicable deferred edits

None for 2b.2a (shipped). 2b.2b is schema + UI + Layer 1 plumbing — spec §10 slice 2b.2 row has the file-by-file plan.

## 8. Summary

Plan #60's stall was a feasibility gap in slice 2b's grid, not a regression. The grid now caps weekly sessions at a deterministic, athlete-controlled, days-derived ceiling (default Peak 10, near-flat phase scaling, hard 2×days clamp), sheds lowest-priority disciplines first, and preserves volume. The athlete now owns their rest days (§5.4 nudge removed). Deterministic, no LLM. The re-run is the proof, owed Andy's-hands after merge.
