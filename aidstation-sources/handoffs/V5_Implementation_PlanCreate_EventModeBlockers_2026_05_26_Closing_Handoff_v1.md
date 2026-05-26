# plan-create event-mode blockers — Closing Handoff

**Session:** Diagnosed + fixed a live "Plan generation failed unexpectedly" report, then swept the cone for the next forward blockers. The `layer4_cache` CHECK fix (#177) let generation run *past* the 3A cache write in production for the first time, exposing a chain of latent faults in the never-before-run stretch (`3B → 2E → Layer 4 driver → persist`). Root cause of the report: `Layer3BInputError("event_mode_missing_goal_outcome")` — a `ValueError` subclass that escaped the route's `*OutputError`-only catch into the generic catch-all. Forward sweep found two more near-certain blockers (`discipline_weights_invalid` from a 2A↔Layer4 weight-scale contradiction; `time_to_event_weeks_mismatch` for future start dates) + a raw-500 persist seam. All fixed.
**Date:** 2026-05-26
**Predecessor handoff:** `V5_Implementation_Layer4_CacheEntryPointCheckFix_2026_05_26_Closing_Handoff_v1.md` (§the `layer4_cache` entry_point CHECK drift fix, PR #177 `86742fc`)
**Branch:** `claude/vigilant-gates-uH4qI`
**PR:** #178 (2 commits)
**Status:** 4 substantive files (`layer3b/cached_wrapper.py`, `routes/plan_create.py`, `layer2a/builder.py`, `layer4/orchestrator.py`) + 4 test files + bookkeeping. Full suite **1714 passed / 16 skipped** (+4 over the 1710 baseline).

---

## 1. Session-start verification (Rule #9)

| Claim (predecessor) | Anchor | Result |
|---|---|---|
| PR #177 merged to `main` (`86742fc`) | `git log` | ✅ present; branch base |
| `_advance_plan_generation` catch-all + constraint repair migration present | grep | ✅ present |

Andy reported the live symptom directly (migration applied + redeployed, then "Plan generation failed unexpectedly"), so the session was bug-driven, not roadmap-driven (§6.3 notifications still pending).

## 2. Session narrative

Andy applied the #177 migration to Neon, verified the constraint lists all 7 entry points, redeployed, and a new plan still failed — but with a **different** message: "Plan generation failed unexpectedly. Please try again or contact support." That string is the `_advance_plan_generation` catch-all (`routes/plan_create.py:280`), not the earlier `schema_violation` panel — so the constraint fix worked and the cone now ran past the (previously fatal) 3A cache write for the first time in prod.

The catch-all only `print`s a truncated line and the Vercel runtime-log MCP tool collapses each request to one message, so the exception type wasn't directly readable. Diagnosed by **full-text-search elimination** against the failed `POST /plans/v2/17/generate` request: the search reliably matches mid-message substrings (confirmed via `generation`), and `Layer3BInputError` + `event_mode_missing_goal_outcome` both matched while `*OutputError` / the builtins did not. Root cause confirmed: the shared full cone (`_upstream_full_cone`) calls Layer 3B without a `goal_outcome`, but 3B's event-mode `_validate_inputs` hard-requires one (the §H.2 capture form is the documented "Phase 4 L3B-P-2 §H.2 deployed-shape gap," `CURRENT_STATE.md:117`). `Layer3BInputError` is a `ValueError` subclass, so it fell outside the route's `(Layer3AOutputError, Layer3BOutputError)` catch → catch-all.

Andy then asked to sweep the backlog + the newly-reachable cone for blockers not yet hit. Audit (`3B → 2E → Layer 4 driver → persist`) found:
- **`discipline_weights_invalid`** — 2A's `load_weight` is the midpoint of the **0–100** `race_time_pct` band (spec example `25.0`/`15.0`; ETL `sum_to_100` validator), so included disciplines sum to ~100, but Layer 4 `_validate_plan_create_inputs` requires ~1.0 (`Layer4_Spec §4.2`). Already flagged unresolved in `CURRENT_STATE.md:90`. Near-certain next wall.
- **`time_to_event_weeks_mismatch`** — 3B was called with `current_date=today` but Layer 4 validates 3B's `time_to_event_weeks` against `plan_start_date`; a future start date diverges by the offset.
- **Persist seam** — the success-path `persist_layer4_sessions` ran *outside* `_advance_plan_generation`'s `try`, so a `plan_sessions` write failure would 500 (raw) + leave the row `generating` for the cron to re-pick.

Verified sound (not blockers): phase vocabulary aligned across 3B/2E/phase_structure (`Base/Build/Peak/Taper`); 2E consumes `load_weight` only as a ratio (scale-invariant — normalizing won't change nutrition); `maxDuration=300s` (Pro) set.

Andy approved (AskUserQuestion): normalize `load_weight` **in 2A**, + both secondary items (3B date, persist wrap).

## 3. File-by-file edits

### 3.1 `layer3b/cached_wrapper.py` (modified)
- New module constant `_DEFAULT_EVENT_GOAL_OUTCOME = "Finish"` + an `elif goal_outcome is None:` back-fill in the event-mode branch (mirrors the existing no-event-mode back-fill). Feeds both `_validate_inputs` and the deterministic `section_h2_kwargs` / cache key. Fixes all three full-cone entry points (race_week_brief / plan_refresh / plan_create).

### 3.2 `routes/plan_create.py` (modified)
- Broadened the typed catch to `(Layer3AInputError, Layer3BInputError, Layer3AOutputError, Layer3BOutputError)` (+ `import traceback`, + `Layer3AInputError`/`Layer3BInputError` imports), logging `exc.code` + `exc.detail`; added `traceback.print_exc()` to the catch-all.
- Moved the success path (DELETE-guard + `persist_layer4_sessions` + `ready` flip + commit) **inside** the `try`, so a persist/commit failure is caught + marks the row terminal instead of a raw 500.

### 3.3 `layer2a/builder.py` (modified)
- New `_normalize_load_weights(disciplines)` helper: divides every discipline's `load_weight.value` AND `system_default` by the included-set total (preserves the value/system_default ratio; no-op when the total is non-positive). Called in `q_layer2a_discipline_classifier_payload` **after** `_emit_coaching_flags` so the athlete-override divergence flag still reads the raw 0–100 `override_pct`. Result: included `load_weight` sums to ≈1.0 (`Layer4_Spec §4.2`).

### 3.4 `layer4/orchestrator.py` (modified)
- `_upstream_full_cone` gains `viability_current_date: date | None = None`, used only for 3B's `current_date` (`= viability_current_date if not None else today`). `orchestrate_plan_create` passes `viability_current_date=plan_start_date`. 3A's `as_of` + 2E stay on `today`; race_week_brief / plan_refresh unchanged.

### 3.5 Tests (modified)
- `tests/test_layer3_cached_wrappers.py` — 2 new: event-mode back-fills `"Finish"` when omitted; explicit `goal_outcome` preserved.
- `tests/test_layer2a.py` — updated 2 assertion spots to the normalized contract (included sum ≈1.0 via `pytest.approx`; override ratio preserved instead of raw `25.0`/`15.0`).
- `tests/test_layer4_orchestrator.py` — 1 new: 3B `current_date == plan_start_date` while 3A `as_of.date() == today`.
- `tests/test_routes_plan_create.py` — 1 new: a `persist_layer4_sessions` failure marks the row `failed` (catch-all), not `ready` / raw 500.

## 4. Code / tests

Full suite **1714 passed / 16 skipped** in a fresh `/tmp/venv`. +4 over the 1710 baseline: +2 (3B goal_outcome back-fill), +1 (3B-date anchor), +1 (persist-failure). `test_layer2a` edits modified existing assertions (no count change). `py_compile` clean on all 4 substantive files. (DB egress to Neon is blocked from the container; PyPI egress works — tests run, no live DB.)

## 5. Owed action (Andy's hands)

**None for code** — no migration (code-only). After the PR #178 deploy, the clean test is a real `/plans/v2/new` for an athlete **with a target race** (event mode): 3B caches with `goal_outcome="Finish"` (no `Layer3BInputError`), 2A weights pass Layer 4's `_validate_plan_create_inputs`, the cone reaches Layer 4 per-phase synthesis, and the plan completes. The stale row 17 stays terminal-`failed` — start a fresh plan. Start date = today is simplest (the 3B-date fix covers future starts).

## 6. Next session pointers

### 6.1 Spec reconciliation (doc-only — owed, deferred this session)
The `load_weight` normalization reconciles a real **`Layer2A_Spec §5.4` ↔ `Layer4_Spec §4.2`** scale contradiction (2A computed a 0–100 midpoint; Layer 4 §4.2 + `_validate_plan_create_inputs` expect ≈1.0). Code now emits 0–1; the spec text + the `CURRENT_STATE.md:90` residual still describe the old 0–100 scale. Reconcile: `Layer2A_Spec §5.4` (note the emitted `load_weight` is normalized to a 0–1 distribution over the included set; the raw midpoint is the pre-normalization basis; the override-divergence flag reads the raw band) + clear the `CURRENT_STATE.md:90` residual. Held out of PR #178 to keep it code-scoped + respect Rule #12 (spec version-suffix).

### 6.2 Residual — Layer 2E athlete-data gates (data, not wiring)
2E `_validate_inputs` (`layer2e/builder.py:302-311`) requires `performance.body_weight_kg` + `identity.height_cm` present + positive. Missing → `Layer2EInputError` → catch-all (now with a traceback). Confirm Andy's profile has both before the live test; not a code gap.

### 6.3 Architect-recommended next forward move — §6.3 email + in-app notifications
Unchanged from the predecessor chain: on terminal status in `_advance_plan_generation` (the single terminal hook for poller + cron), send a "plan ready"/"plan failed" email (`email_helper.py`) + a dashboard status badge; guard double-send (transition-into-terminal only, or a `notified_at` column).

### 6.4 Watch — uncached seam/validator tail + concurrent poller/cron (carried)
`_run_pattern_a_engine`'s seam-review + final-validator tail is still uncached (re-runs whole on each resume); the poller + cron can run the same row concurrently. Pro 300s makes a kill-and-resume tractable, but if cost/latency bites, cache the seam tail and/or bound the cron to one row + a wall-clock budget.

### 6.5 Operating notes (read order — Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling items.
4. This handoff.
5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Back-fill 3B `goal_outcome` to `"Finish"` in event mode when omitted | Claude | No capture form / column exists (deployed-shape gap); "Finish" is the conservative tier; mirrors the no-event back-fill; fixes all 3 full-cone entry points at one site. |
| 2 | Catch `Layer3*InputError` in `_advance_plan_generation` + add a catch-all traceback | Claude | They're `ValueError` subclasses outside the `*OutputError` contract; converts an opaque "unexpected" into a coded message + makes the next surprise diagnosable (the §6.1 detail-capture the predecessor deferred). |
| 3 | Normalize `load_weight` **in 2A** (not the Layer 4 validator) | Andy | Andy's call between the two sides of the contradiction; 2A emits the normalized 0–1 distribution as the contract. Implemented with same-divisor scaling so the override flag + 2E ratio use stay correct. |
| 4 | Anchor 3B `current_date` on `plan_start_date` for plan_create only | Andy | The training timeline starts at `plan_start_date`; makes 3B's `time_to_event_weeks` consistent with Layer 4's `(event_date - plan_start_date)//7` check for future starts. 3A `as_of`/2E stay on `today`. |
| 5 | Move persist + ready-flip inside the `try` | Andy | A `plan_sessions` schema/natural-key surprise should degrade gracefully, not 500 + leave the row `generating` for the cron. |
| 6 | Defer the spec-text + `CURRENT_STATE.md:90` reconciliation to a doc-only follow-on | Claude | Keeps PR #178 code-scoped; spec edits carry the Rule #12 version-suffix convention + are Andy's design artifact. |

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_DEFAULT_EVENT_GOAL_OUTCOME = "Finish"` + event-mode back-fill in `layer3b/cached_wrapper.py` | ✅ |
| `(Layer3AInputError, Layer3BInputError, Layer3AOutputError, Layer3BOutputError)` catch + `traceback.print_exc()` in `routes/plan_create.py` | ✅ |
| Success path moved inside `_advance_plan_generation`'s `try` | ✅ |
| `_normalize_load_weights` defined + called after `_emit_coaching_flags` in `layer2a/builder.py` | ✅ |
| `viability_current_date` kwarg on `_upstream_full_cone`; `orchestrate_plan_create` passes `plan_start_date` | ✅ |
| 4 test files updated/added; full suite `pytest tests/` → 1714 passed / 16 skipped | ✅ (fresh `/tmp/venv`) |
| Working tree clean after commit | ✅ |

## 9. Files shipped this session

**Substantive (4 files):**
1. `layer3b/cached_wrapper.py`
2. `routes/plan_create.py`
3. `layer2a/builder.py`
4. `layer4/orchestrator.py`

**Tests:**
5. `tests/test_layer3_cached_wrappers.py`
6. `tests/test_layer2a.py`
7. `tests/test_layer4_orchestrator.py`
8. `tests/test_routes_plan_create.py`

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

**End of handoff.**
