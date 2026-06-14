# V5 Implementation — WS-E2: deterministic strength-saturation cap (Closing Handoff)

**Session:** Shipped the §7 WS-E2 saturation backstop — the last code workstream on the feasibility-saturation / locale-retirement north-star plan. A deterministic, pre-synthesis grid pass that caps weekly **failover** strength at `dose + 2` and reallocates the excess to feasible disciplines proportional to load_weight (variety-respecting, volume-conserving).
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSBC_LocaleRetirement_OnboardingHome_2026_06_14_Closing_Handoff_v1.md` (WS-B/WS-C complete, #589 merged).
**Branch / PR:** [#590](https://github.com/ahorn885/exercise/pull/590) (`claude/next-slice-implementation-37iur2`). **Squash-merged to `main`, CI-green.** Closes WS-E2 ([#584](https://github.com/ahorn885/exercise/issues/584)).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§7 WS-E2).
**Status:** 3 substantive code/template files + 1 new test — **within the 5-file ceiling.** No DDL.

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the WS-B/WS-C §8 table — **all ✅, working tree clean, no drift.** Spot-checked: `routes/locales.py` has no `LOCALES` (grep clean), `routes/onboarding.py` carries `locales_continue` + `preferred`. The branch was the fresh harness-pinned `claude/next-slice-implementation-37iur2` (its name matches this scope — no rename needed).

Scope was a genuine decision (WS-B/C done; the carried T3-refresh verify is Andy's-hands-only; E2/H/V all open). Asked Andy via `AskUserQuestion` — he picked **WS-E2 (design + sign-off, then build)**.

---

## 2. Session narrative

- **Why E2 now.** Of the plan's remaining workstreams, E2 was the one with a clear solo build path once the design was ratified. WS-H needs new DDL → design-first + a Neon write (Andy's hands); WS-V is a large durable arc; the carried T3-refresh verify is Andy's-hands (diag token + log paste, Rule #14). E2 trips Trigger #1 (a prompt edit) + #5 (cascade/architecture), so it was a mandatory stop-and-ask — I produced a grounded design (options, tradeoffs, recommendation, gut check) and waited.
- **The honest framing (gut check I gave Andy).** WS-D already proved the pv=69 saturation root cause was a craft source-of-truth drift, **fixed by WS-G** (set B populated → disciplines resolve to real terrain, not strength). E1/#579 already prevents the *crash* (same-day strength collision). So E2 is **quality + defense-in-depth**, not a live-blocker — it stops a *genuinely* over-constrained athlete from getting a periodization-backwards 7-strength week, deterministically. Tier-3/4, not Tier-2. Andy chose to build it anyway.
- **The architectural decision (Trigger #5).** The transform is inherently per-(phase,week) and must run **pre-synthesis**, because "reallocate with variety" means handing the freed time to other feasible disciplines as real cardio — which only works if session **counts** are adjusted before the LLM composes. A post-synthesis repair (the E1 seam) can only **drop** over-cap strength (loses training time), contradicting Andy's §7 "reallocate, respect variety." Andy ratified the **pre-synthesis grid pass**.
- **The variety mechanism (Trigger #5).** I recommended a flat +1-per-discipline absorption cap; Andy chose **proportional-to-load_weight**. I realized it as **d'Hondt highest-averages** apportionment across feasible absorbers (deterministic, proportional, respects per-discipline capacity), and kept his §7 "cap how much any one can absorb" as a per-discipline ceiling: **a discipline can at most double in one reallocation pass.** Excess beyond capacity stays as (capped) strength.
- **Grounded every edit against the live files** — the cascade (`session_feasibility.py`), the grid (`session_grid.py`), the E1 crash-guard + grid render (`per_phase.py`), the dose constant + advisory rule (`validator.py`), and the shared prompt (`strength_guidance.py`). The dose arithmetic was the one subtlety: the programmed dose is **prompt-added, not in the grid**, so capping total at `dose+2` reduces to **a flat +2 failover headroom in every phase** (the dose cancels). Caught + fixed mid-build via a failing-assertion test.

---

## 3. File-by-file edits

### 3.1 `layer4/session_grid.py` (modified — core)
- **New pure `apply_strength_saturation_cap(allocations, phase_name, feasibility_tiers, discipline_weights, skill_gated_ids=frozenset())` → `(adjusted_allocations, log_detail)`.** Algorithm: `allowed_failover = max(0, 2 − grid_strength)`; `failover_total = Σ` sessions of strength-tier disciplines (excluding the literal `strength` alloc + skill-gated); `over = failover_total − allowed_failover`. If `over ≤ 0` → identity return. Else trim `min(over, total_capacity)` failover sessions **lowest-priority-first** (tail of the priority-ordered list) and distribute them to feasible absorbers (tier ∈ {exact,proxy,indoor} **or** absent/unconstrained, not skill-gated) via **d'Hondt** (`weight / (assigned+1)`, tie → higher weight then higher priority), each capped at `floor(count × 1.0)` (the double rule). Excess that won't fit stays as strength. Adjusted allocations carry a `cadence_note` ("strength capped at dose+2 — N reallocated" / "+N reallocated from over-cap strength").
- **Constants:** `_FAILOVER_STRENGTH_HEADROOM = 2`, `_REALLOCATION_ABSORB_MULTIPLE = 1.0`, `_DEFAULT_ABSORB_WEIGHT = 1.0`, `_FEASIBLE_TIERS = {exact,proxy,indoor}`.
- **Import:** `_STRENGTH_SESSIONS_PER_WEEK as _STRENGTH_DOSE_PER_WEEK` from `validator` (single-sources the dose; `validator` does NOT import `session_grid`, so no cycle).
- **`SessionGrid` dataclass:** new `saturation_note: str | None = None` field (Rule #15 carrier).
- **`build_session_grid`:** two new kwargs `strength_feasibility_tiers: dict[str,str] | None = None` + `skill_gated_ids`. After `apply_session_ceiling`, when tiers are supplied, runs the cap and stashes the detail on `SessionGrid.saturation_note`. Captures `discipline_weights = {id: load_weight.value}` from the included set. Bare callers omit the kwarg → no cap (mirrors the `available_days`-gated ceiling). `apply_strength_saturation_cap` added to `__all__`.

### 3.2 `layer4/per_phase.py` (modified — wiring + Rule #15)
- In `_format_session_grid`, the `build_session_grid(...)` call now passes `strength_feasibility_tiers={d: r.tier for d,r in terrain_feasibility.items()}` (None when no feasibility) + `skill_gated_ids=frozenset(skill_gated or {})` — both already in scope as function params.
- After the existing `build_session_grid:` debug print, a Rule #15 line: `if grid.saturation_note: print(f"strength_saturation_cap: {phase_name}:w{w} {grid.saturation_note}")`.

### 3.3 `layer4/strength_guidance.py` (modified — Trigger #1)
- The FAILOVER STRENGTH closing bullet's "may push total strength sessions higher in a constrained week. That is acceptable" → now states the cap: "they ARE capped: the grid hands you at most a bounded number of strength sessions per week (the programmed dose plus a small failover headroom) and deterministically reallocates any excess infeasible volume to feasible disciplines before you compose. Compose only the strength sessions the grid gives you, and compose them light." The cap lives in counts; the LLM is not asked to enforce it.

### 3.4 `tests/test_layer4_session_grid_saturation.py` (new)
11 cases: no-op within headroom, unknown-phase no-op, over-cap trim+reallocate, proportional split (3:1 weights → d'Hondt 3 and 1), absorption-cap + residual-stays-strength, no-feasible-absorber leaves strength unchanged, lowest-priority-failover-trimmed-first, skill-gated excluded from trim+absorb, unconstrained-discipline is a valid absorber, + 2 `build_session_grid` integration tests (cap fires & sets `saturation_note`; no cap without tiers). All assert **volume conservation**.

---

## 4. Code / tests

**Full suite green: 2391 passed, 30 skipped, 2 pre-existing unrelated warnings** (`test_layer3b_builder` evidence-basis — same as the predecessor session). Affected suites all green: `test_layer4_session_grid`, `test_layer4_strength_frequency`, `test_layer4_strength_collision_repair`, `test_layer4_strength_templates`, `test_layer4_terrain_feasibility_wiring`, `test_layer4_plan_create`, `test_layer4_craft_feasibility`, `test_layer4_session_feasibility`.

---

## 5. Manual verification

No SQL. **No new cache surface** — the cap is a pure function of inputs already in `plan_create_key`: the feasibility tiers (folded via `compute_terrain_feasibility_hash`, #556) and the skill-gated set (deterministic from `layer2c_hash`, #336). So no `LAYER4_PROMPT_REVISION` bump is owed for the count change; the `strength_guidance.py` text edit *does* change the prompt body — **but** the prompt text isn't in the key directly (only `LAYER4_PROMPT_REVISION` is). A capped plan will only re-synthesize cold if the inputs change; the prompt-text correction lands on the **next cold synth** like any prompt edit. *(If Andy wants the corrected failover wording to take effect on already-cached plans immediately, bump `hashing.LAYER4_PROMPT_REVISION` — I did NOT, since the wording is a clarification, not a behavior change: the behavior change is in the deterministic counts, which ARE keyed.)*

The live behavior (an over-constrained week capping to dose+2 + reallocating) is a good **next-session Andy's-hands check** on the preview/prod URL via `/admin/logs?q=strength_saturation_cap` on the next cold plan-create — but not owed for merge (behavioral correctness pinned by the 11 tests).

---

## 6. Next session pointers

### 6.1 This slice
WS-E2 **shipped + squash-merged to `main`** on #590 (CI-green, no DDL). Plan §2 table flipped to SHIPPED; §7 carries the build note. Issue [#584](https://github.com/ahorn885/exercise/issues/584) closed (`completed`, PR #590).

### 6.2 Next forward moves (4-tier order)
- **STILL OWED (carried, Tier 1):** the post-#572 live **T3 *refresh*** re-verify (paired: diag token + Andy pasting logs, Rule #14). Never live-verified post-#572; pv=71 was a *create*.
- **Tier-4 remaining on this plan:** **WS-V** the full Vocabulary arc (`Vocabulary_TargetState_and_Plan_v1`) — durable one-source-of-truth cleanup; **WS-H** away-craft availability (needs DDL → design-first, Trigger #3, + a Neon write Andy applies).
- **Off-plan:** **#542** nutrition macros (protein g/kg too low — clean solo bug fix, no trigger), **#543** health-condition dropdown (Trigger #2 vocab add — needs Andy to ratify the condition list), the compliance build-out (epics #353/#355/#356/#359).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules (incl. Rules #14/#15).
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — top entry.
4. This handoff.
5. The plan `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§7).
6. `./scripts/verify-handoff.sh` (run from `aidstation-sources/`).

**Test env:** `pytest` isn't in `requirements.txt` — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then run the full `tests/`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Build WS-E2 this slice (vs T3-verify / #542 / WS-H/V) | Andy (2026-06-14, AskUserQuestion) | The remaining solo-buildable advance on the north-star plan; T3-verify is Andy's-hands, H/V need design/DDL first. |
| 2 | Cap lives in a **pre-synthesis grid pass** (not the post-synthesis E1 seam) | Andy (Trigger #5) | Only a pre-synthesis count transform can reallocate-with-variety; post-synthesis can only drop (loses training time). |
| 3 | Reallocation **proportional to load_weight** (not flat +1/+2 absorb) | Andy (Trigger #5) | His pick over my +1 recommendation; realized as d'Hondt + a per-discipline double-cap so it still can't dump. |
| 4 | Failover headroom is a **flat +2 every phase** | Claude (derived) | `cap = dose+2` total; the prompt-added dose cancels → `allowed_failover = 2 − grid_strength`. Phase-independent. |
| 5 | Excess that won't fit **stays as strength** (never dropped) | Claude | Preserves training time; degrades gracefully; E1/#579 still backstops the same-day crash. |
| 6 | **Skill-gated strength excluded** from cap (trim + absorb) | Claude (flagged) | #336 is a deliberate safety substitution, not a saturation driver; capping it would mis-handle a not-cleared discipline. Documented scope limit. |
| 7 | **No `LAYER4_PROMPT_REVISION` bump** for the prompt-text clarification | Claude | The behavior change is in the (keyed) deterministic counts; the text is a clarification. Bump only if Andy wants the wording live on cached plans now. |

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Cap function | `layer4/session_grid.py` | `def apply_strength_saturation_cap(` present; in `__all__` |
| Headroom const | `layer4/session_grid.py` | `_FAILOVER_STRENGTH_HEADROOM = 2`; `allowed_failover = max(0, _FAILOVER_STRENGTH_HEADROOM - grid_strength)` |
| Dose single-source | `layer4/session_grid.py` | imports `_STRENGTH_SESSIONS_PER_WEEK as _STRENGTH_DOSE_PER_WEEK` from `validator` |
| Grid field | `layer4/session_grid.py` | `SessionGrid.saturation_note: str \| None = None` |
| Grid wiring | `layer4/session_grid.py` | `build_session_grid` has `strength_feasibility_tiers=` + `skill_gated_ids=`; calls the cap after `apply_session_ceiling` |
| Per-phase wiring | `layer4/per_phase.py` | `build_session_grid(...)` passes `strength_feasibility_tiers=` + `skill_gated_ids=` |
| Rule #15 log | `layer4/per_phase.py` | `print(f"strength_saturation_cap: ...")` guarded on `grid.saturation_note` |
| Prompt (Trigger #1) | `layer4/strength_guidance.py` | failover bullet says "they ARE capped"; no "may push total strength sessions higher … acceptable" |
| Tests | `tests/test_layer4_session_grid_saturation.py` | 11 cases; `apply_strength_saturation_cap` + `build_session_grid` integration |
| Suite | — | `pytest tests/` → 2391 passed, 30 skipped |
| Working tree | — | clean after the bookkeeping commit |

---

## 9. Files shipped this session

**Substantive (3 + 1 test):**
1. `layer4/session_grid.py`
2. `layer4/per_phase.py`
3. `layer4/strength_guidance.py`
4. `tests/test_layer4_session_grid_saturation.py`

**Bookkeeping (this commit):** `CURRENT_STATE.md`, `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§2 table + §7), this handoff.

---

## 10. Owed Andy's hands (Neon — container has no egress)

**None.** This slice added no DDL and made no Neon write. (Carried, unrelated: the post-#572 live T3 *refresh* re-verify.)
