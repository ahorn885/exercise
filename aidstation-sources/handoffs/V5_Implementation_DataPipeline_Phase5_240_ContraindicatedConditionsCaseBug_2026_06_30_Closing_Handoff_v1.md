# V5 Implementation — Data-Pipeline Campaign, Phase 5: #240 — Closed Not-Planned + Adjacent Bug Fix — Closing Handoff (2026-06-30)

**Branch:** `claude/phase-5-data-pipeline-lkly66`
**PR:** not yet opened — pushed + bookkept, awaiting Andy's go (project rule: no auto-open)
**Campaign kickoff:** `handoffs/DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`
**Issues:** [#240](https://github.com/ahorn885/exercise/issues/240) **closed not_planned**; [#1098](https://github.com/ahorn885/exercise/issues/1098) **filed** (unrelated finding, not fixed)

---

## 1. What happened — #240 didn't survive contact with the real data

The campaign kickoff planned Phase 5 as a Phase-4-style mechanical promotion: a new `layer0.injury_flag_categories` table (family 0A per the kickoff; corrected to **0B** during this session since the table would be keyed by exercise, matching `exercises`/`sport_exercise_map`), seeded by classifying `injury_flags_text` into cardiac/cognitive/skin/recovery categories.

Before building anything, this session pulled the actual data to ground the design (Rule re: "never invent file contents"). Two background research agents + direct SQL parsing of `etl/output/layer0_etl_v1.10.1.sql` confirmed:

- #240 is the GitHub-issue form of backlog item **D-37** (`archive/backlog/Project_Backlog_v62.md`, `specs/Layer0_ETL_Spec_v8.md` §9, surfaced 2026-05-11). D-37's real category list is cardiac / cognitive / surface-tissue (skin) / recovery-state / **equipment-criticism** — Andy had already ruled equipment-criticism out of scope ("equipment-quality calls belong to the athlete"), explaining why the GitHub issue lists only 4 categories.
- Of the **199 active exercises**, only **10 text segments anywhere** mention anything cardiac/cognitive/skin/recovery-flavored. Of those 10: 5 are normal first-time-DOMS soreness notes (not injury risk), 1 is a footwear comment, 1 is a body-part mis-tag, and the remaining 2 ("Cognitive — sequence errors..." on two transition drills) are soft caution language with no implied prescription change.
- The consumption side was out of scope for this phase regardless — the issue's own body says "so the validator can act on them instead of free text" is **deferred to v2**. Building the table now would have produced data with zero readers — the exact orphaned-structured-field anti-pattern issue **#298** already flagged on this same table family (`ResolvedExercise.contraindicated_parts`/`contraindicated_conditions` "emitted but unconsumed").

Presented this to Andy (AskUserQuestion, plain-language restated per his request) with the full 10-row table. **Andy's call: "bug fix only. drop the injury flags text crap entirely. we wont use it."** #240 closed not_planned with the findings recorded in the closing comment so a future session doesn't re-derive this from scratch.

**No migration shipped.** Next migration number is still `0038` (confirmed `0037` was already claimed by an unrelated merged fix, [#1090](https://github.com/ahorn885/exercise/pull/1090) "exclude climbing disciplines from default AR plan" — the kickoff's "next is 0037" note was stale).

---

## 2. What shipped instead — `contraindicated_conditions` case-mismatch bug fix

While grounding the #240 investigation, found a real, live correctness bug adjacent to (but independent of) `injury_flags_text`.

### The bug

`layer0.exercises.contraindicated_conditions` is a **different, pre-existing** column (fed from a separate legacy XLSX source column, not `injury_flags_text`). Contrary to two stale notes claiming it's "currently unpopulated" (`layer2d/builder.py` lines 24-30 pre-fix; `CURRENT_STATE.md`), it IS populated — **~218 historical rows** (~14-19 distinct active exercises) carrying values like `Cardiac`, `Cognitive`, `Neurological`, `Respiratory`, `Skin`.

These are stored in **Title Case**, matching `layer0.health_condition_categories.category_name` (the canonical display vocabulary — 12 rows including a "Cognitive" / "Cognitive / Mental health" duplication). `HealthConditionRecord.system_category` (the athlete's own condition tag) is a **lowercase snake_case 11-value enum** (`cardiac`, `respiratory`, `endocrine_metabolic`, `gi`, `neurological`, `cognitive_mental_health`, `musculoskeletal`, `skin`, `thermoregulation`, `immune_autoimmune`, `other`).

`_condition_verdict()` (`layer2d/builder.py`) compared these two vocabularies **directly**, with no normalization:

```python
contra = set(exercise.get("contraindicated_conditions") or [])
...
if cond.system_category in contra:   # "cardiac" in {"Cardiac"} → always False
```

So this safety check — which drives real volume/intensity/tempo accommodations via `_recommend_accommodations` — has likely **never fired** for any athlete, regardless of condition. Confirmed the existing test (`tests/test_layer2d.py::TestRespiratoryAccommodation`) only ever exercised this with lowercase input (`contraindicated_conditions=["respiratory"]`), bypassing the real Title-Case data shape and giving false confidence.

Worth flagging: "Cognitive" (no "/ Mental health") is the **single most-used** value in the real data, and has **no literal lowercase match at all** in the 11-value enum — even a plain `.lower()` fix wouldn't have closed this; it needed an explicit vocabulary mapping.

### The fix (`layer2d/builder.py`)

Added `_CONTRAINDICATED_CONDITION_TO_SYSTEM_CATEGORY: dict[str, str]` — maps all 12 known `health_condition_categories.category_name` values (lowercased) to the 11 `system_category` slugs, collapsing both "Cognitive" and "Cognitive / Mental health" to `cognitive_mental_health`. `_condition_verdict()` now normalizes `contraindicated_conditions` through this map before the membership check. Docstring (lines 24-36) corrected to drop the stale "unpopulated" claim and document the real shape.

**Code-only fix, no migration.** The stored data already matches its own canonical vocabulary (`health_condition_categories.category_name`, validated by the existing `etl/layer0/validation/contraindicated_conditions.py` gate, case-insensitively) — the bug was in the *consumer*, not the data. No `layer0-apply` owed.

**Spec sync:** `Layer2D_Spec_v1.md` §5.3.2 pseudocode carried the identical bug (a naive `set(...)` membership check) — updated to match the fix.

### Tests (`tests/test_layer2d.py`)

New `TestContraindicatedConditionTitleCaseNormalization` (3 cases): Title-Case `"Cardiac"` → matches `system_category="cardiac"`; Title-Case `"Cognitive"` → matches `system_category="cognitive_mental_health"` (the real, trickiest case); an unrelated `system_category` stays clean. All exercise verdicts confirmed via `payload.accommodated_exercises`, not just the verdict string, so the full `_recommend_accommodations` path is covered.

---

## 3. Verification

- **`python -m pytest tests/test_layer4_orchestrator.py tests/test_layer2d.py -q`** → 120 passed
- **`python -m pytest tests/ etl/tests/ -q`** → **4136 passed, 30 skipped** (only the 3 pre-existing `#217` warnings)
- **`ruff check layer2d/builder.py tests/test_layer2d.py`** → 4 pre-existing unused-import findings (confirmed via `git stash` diff — identical on `main`, none introduced by this session)

---

## 4. Adjacent finding — filed, not fixed

**[#1098](https://github.com/ahorn885/exercise/issues/1098):** `Layer2D_Spec_v1.md` §6 item 2D-2 claims movement-constraint matching was migrated from `injury_flags_text` keyword-search to a structured `movement_components TEXT[]` set-intersect, "Closed (FC-1b, 2026-05-12), 159/159 rows populated." Confirmed via direct query: **0/199 active exercises** have `movement_components` populated, and `layer2d/builder.py` has zero references to the column — the live code is still `_movement_constraint_verdict()` doing keyword-match against `injury_flags_text`. Not urgent (no user-facing bug, the keyword-match path works, just less precisely) — filed so it's tracked rather than silently re-discovered. **Out of scope for this session** ("bug fix only" was Andy's explicit instruction); not touched.

---

## 5. Owed after this lands

Nothing code-side. Bookkeeping (this handoff + `CURRENT_STATE.md` + `CARRY_FORWARD.md` + issue reconciliation) is riding the same branch per the project's PR-gated operating flow. **PR opens on Andy's go** — no auto-open.

**Next campaign step (Phase 6, future session):** close epic #261 (only remaining listed children beyond #269, which is now closed, need a status check — kickoff assumed #269 was the only open one but #261 lists 10 sub-issues total) and comment on/close #228 per the kickoff's original Phase 6 note. Not started this session — Andy scoped this session to the bug fix only.

---

## 6. Bookkeeping (Rule #10)

### §6 anchor table

| Claim | File | Anchor |
|---|---|---|
| Case-mismatch fix present | `layer2d/builder.py` | `grep "_CONTRAINDICATED_CONDITION_TO_SYSTEM_CATEGORY" layer2d/builder.py` → dict def + 1 use site in `_condition_verdict` |
| Stale "unpopulated" claim removed | `layer2d/builder.py` | `grep -i "currently unpopulated" layer2d/builder.py` → 0 hits |
| Spec pseudocode synced | `aidstation-sources/specs/Layer2D_Spec_v1.md` | §5.3.2 — `grep "CONDITION_CATEGORY_TO_SYSTEM_CATEGORY" aidstation-sources/specs/Layer2D_Spec_v1.md` → present |
| Regression tests present | `tests/test_layer2d.py` | `grep "TestContraindicatedConditionTitleCaseNormalization" tests/test_layer2d.py` → class + 3 test methods |
| Suite green | `tests/` + `etl/tests/` | `python3 -m pytest tests/ etl/tests/ -q` → 4136 passed / 30 skipped |
| #240 closed not_planned | GitHub | issue #240 state=closed, state_reason=not_planned, closing comment present |
| #1098 filed | GitHub | issue #1098 open, labels `type:bug`/`layer:2d`/`layer:0`/`priority:low` |
| No migration this session | `etl/migrations/layer0/` | unchanged; next migration is still `0038` (`0037` already taken by unrelated PR #1090) |

### Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (data-pipeline campaign entry, now pointing at Phase 6)
4. This handoff + the campaign kickoff (`DataPipeline_Phase1-2_Done_Phase3-6_Kickoff_Handoff.md`)
5. `./scripts/verify-handoff.sh` — automated anchor sweep
