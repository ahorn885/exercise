# V5 Implementation — #648 Standing exercises-FK validator for `validate_layer0` — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/layer0-exercises-fk-validator-648`
**New file:** `etl/layer0/validation/exercises_fk_check.py`
**PR:** _(opened this session — see GitHub; auto-merges on green)_
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_CullTechnicalSkill_644_2026_06_16_Closing_Handoff_v1.md` (#644, PRs #647/#650).

Session opened on the #644 closing handoff ("V5_Implementation_Locations_CullTechnicalSkill_644… let's work!"). Rule #9 sweep clean (handoff anchors all ✅; tree clean). #644 + #623 confirmed closed completed (PR #650 merged). Andy chose **#648** (exercises-FK validator) over #619 (Locations/nav IA) and the T3-refresh re-verify, via `AskUserQuestion`.

---

## 1. What shipped — #648

### The gap (found during #644)
`validate_layer0` FK-checks **only the disciplines family** (`etl/layer0/validation/fk_checks.py` — `discipline_substitutes`, `discipline_training_gaps`). **Nothing validated the exercises graph.** There was no check that, for active `layer0.exercises`:
- `progression_exercise_id` (when set) resolves to an active exercise,
- `regression_exercise_id` (when set) resolves to an active exercise,
- each `physical_proxies[].exercise_id` resolves to an active exercise,
- each active `sport_exercise_map.exercise_id` resolves to an active exercise.

(`vocab_alignment.py` checks only `sport_exercise_map.sport_name` vs the bridge and `exercises.contraindicated_parts` vs `body_parts` — not exercise_id refs.)

**Why it matters:** retiring/superseding an exercise can orphan a *kept* exercise still pointing at it. The 2C/2D readers filter `e.superseded_at IS NULL` on the **direct** exercises join (`layer2c/builder.py` ~L298, `layer2d/builder.py` ~L872), so a stale `sport_exercise_map` row goes inert on its own — but a dangling `physical_proxies`/progression/regression ref on an **active** row would surface (Tier-3 proxy resolution / progression-regression display) and the gate would not catch it. The cull migrations `0007`/`0008`/`0009` each **hand-rolled** these FK assertions in their own DO-block (fragile — the next migration author has to remember).

### The build (1 substantive new file + 2 edits)
- **`etl/layer0/validation/exercises_fk_check.py`** (NEW) — `run_exercises_fk(conn)`:
  - loads the active-exercise id set once (`SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL`),
  - scans active exercises for non-empty `progression_exercise_id` / `regression_exercise_id` not in that set,
  - unnests `physical_proxies` (`jsonb_array_elements`, guarded `jsonb_typeof(...) = 'array'`) and checks each `exercise_id`,
  - scans active `sport_exercise_map` rows whose `exercise_id` is not in the set,
  - returns the standard `{rows_checked, pass_count, error_count, errors}` shape; each error carries `{ref_kind, holder, holder_name, missing_id}`.
- **`etl/layer0/validate_layer0.py`** — import `run_exercises_fk`; add `_v_exercises_fk` extractor (Violation id `"{ref_kind}:{holder}->{missing_id}"`, fix-not-waive); register `Check("exercises_fk", …)` **3rd in `CHECKS`** (after the two disciplines FK checks). Registry is now **11 entries**.
- **`etl/tests/test_validate_layer0.py`** — `exercises_fk` added to `_clean_results()`; registry-count assertion 10→**11** (+`"exercises_fk" in names`); new `test_dangling_exercise_ref_fails_the_gate`; `_v_exercises_fk` id/detail assertions in `test_extractors_produce_expected_ids`.

### Why no DDL / migration / prod apply
This is a **Python validator**, not a data edit. It runs wherever `validate_layer0` runs:
- **CI `layer0-gate`** (`.github/workflows/ci.yml`) loads the newest `etl/output/layer0_etl_v*.sql` baseline, applies `etl/migrations/layer0/*.sql` (`0006`–`0009`), then runs `python -m etl.layer0.validate_layer0` — the new check is driven by the `CHECKS` registry, so **no workflow change**.
- **Nightly `layer0-validate-live`** runs the same gate vs **live** prod via the read-only role — the new check rides it automatically.

The live exercises graph is already clean (the #644 verification confirmed **0 dangling prog/regr/proxy refs, 0 stale `sport_exercise_map` rows**), so the validator passes on the current state. Per-migration DO-blocks are now a redundant belt rather than the only guard.

### Not a Stop-and-ask Trigger
Hardening only — no vocab/exercise-DB entry (Trigger #2), no prompt body (Trigger #1), no cross-layer contract / cache-key change (Trigger #3). Executed directly.

### Verification
- **`etl/tests/` 90 passed** (was 89; +1 the dangling-ref gate test). Unit tests feed synthetic validator-result dicts through the pure `evaluate`/extract/waiver path (no DB) — the validators' live SQL is exercised by the `layer0-gate` CI job.
- Container has the **psql client only** (no local PG server) → **CI is the authoritative live-DB gate** (same constraint as the #644 session). The SQL mirrors `0009`'s proven DO-block column refs (`progression_exercise_id`/`regression_exercise_id`/`physical_proxies`→`exercise_id`/`sport_exercise_map.exercise_id`).

---

## 2. STILL OWED
- **Nothing on #648** once the PR merges — code-only; the validator is live the moment CI/nightly run it. No prod apply step.
- The PR auto-merges on green (CI `layer0-gate` is the real exercise of the new SQL).

## 3. Side-findings
- None new.

## 4. NEXT STEPS — "Locations & Gear" arc
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav/profile IA cleanup (sidebar reorg, profile tabs, supplements tab, Schedule-tab theming, Sources ~3-per-row). Pure UI/IA, `priority:med`. Multi-item — likely splits into slices.
- **Carried (unrelated):** post-#572 live **T3 *refresh*** re-verify (Rule #14 — needs Andy's live hands + diag token).

## 5. Bookkeeping done this session
- **`CURRENT_STATE.md`:** #648 "Last shipped session" entry (names this handoff + the new validator file); #644 demoted to predecessor.
- **GitHub:** #648 commented + **closed completed** on merge (PR ref). New PR opened (auto-merge on green).
- **`CARRY_FORWARD.md`:** no edit.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Validator | `etl/layer0/validation/exercises_fk_check.py` | `def run_exercises_fk(conn)`; `_load_active_exercise_ids`; checks progression/regression/`physical_proxies`/`sport_exercise_map`; returns `{rows_checked, pass_count, error_count, errors}` |
| Wiring | `etl/layer0/validate_layer0.py` | `from etl.layer0.validation.exercises_fk_check import run_exercises_fk`; `_v_exercises_fk` extractor; `Check("exercises_fk", run_exercises_fk, _v_exercises_fk)` 3rd in `CHECKS` (11 entries) |
| Tests | `etl/tests/test_validate_layer0.py` | `"exercises_fk"` in `_clean_results()`; `len(v.CHECKS) == 11`; `test_dangling_exercise_ref_fails_the_gate`; `_v_exercises_fk` id `physical_proxy:EX176->EX094` |
| Precedent | `etl/layer0/validation/primary_movement_check.py` | fix-not-waive validator wired into `validate_layer0` (the `0006` pattern this mirrors) |
| FK gap (now closed) | `etl/layer0/validation/fk_checks.py` | was disciplines-family only; the exercises-FK gap #648 tracked is now covered by the new check |
| CI gate | `.github/workflows/ci.yml` (`layer0-gate`) | baseline + `0006`–`0009`, `python -m etl.layer0.validate_layer0` — new check runs via the registry, no workflow edit |
| Tests run | — | `etl/tests/` 90 passed (container: psql client only → CI is the authoritative live-DB gate) |
| Issue #648 | — | CLOSES completed on PR merge (code-only; no prod apply) |
| Owed | — | none on #648; carried: post-#572 live T3-refresh re-verify (Rule #14) |
