# X2 — Athlete Discipline Weighting end-to-end — Closing Handoff

**Session:** Wired the half-built `athlete_discipline_weighting` feature end-to-end (profile UI + orchestrator unpack into Layer 2A). Third shipped slice of the discipline-mix architecture rewrite (X1a → X1b → **X2** → X3/X4).
**Date:** 2026-06-10
**Predecessor handoff:** `V5_Implementation_Layer0_Slice1_ValidateGate_2026_06_10_Closing_Handoff_v1.md` (the `main` pointer at session start; ran in parallel with this work)
**Branch:** `claude/x2-athlete-discipline-weighting` → PR [#514](https://github.com/ahorn885/exercise/pull/514) squash-merged to `main` (`a284a6d`). This handoff is being closed from `claude/x2-handoff-close`.
**Status:** 5 substantive files (at ceiling). X2 shipped + green on `main`. Earlier this same session also shipped **X1b.3b** (PR [#512](https://github.com/ahorn885/exercise/pull/512), `5f79eca` — craft_discipline_aliases substrate + substitution-group filter).

---

## 1. Session-start verification (Rule #9)

This session ran **in parallel** with the Layer 0 Slice 1 work, so the standard predecessor-anchor sweep is less relevant than the drift it surfaced:

| Claim | Anchor | Result |
|---|---|---|
| `athlete_discipline_weighting` table exists | `init_db._PG_MIGRATIONS` (`UNIQUE(user_id, discipline_slug)`) | ✅ |
| Layer 1 reads it | `layer1.builder._load_discipline_weighting` → `Layer1TrainingHistory.discipline_weighting` (context.py:1850) | ✅ grep |
| Layer 2A accepts athlete overrides | `_compute_load_weight` (`layer2a/builder.py`), `athlete_discipline_overrides` kwarg | ✅ grep |

**Reconciliation note:** `main` drifted **twice** under this branch mid-flight — (1) `#511` "Surface standing nutrition protocol… on the profile" (`1ffffec`) landed a competing block in `templates/profile/edit.html` (resolved at merge — kept both, see §2); (2) `CURRENT_STATE.md` on the branch was stale (06-09) because X1b.3b shipped to `main` without re-pointing it — the Slice 1 session re-pointed it to 06-10. **Lesson for next session: this long branch accumulated drift; X3/X4 should start fresh off `main`.**

---

## 2. Session narrative

**Scope-pick gate.** Andy directed continuing the discipline-mix rewrite from X1b into **X2** (wire the dead `athlete_discipline_weighting`). The read path already existed end-to-end; the two gaps were the **write UI** and the **orchestrator unpack**.

**The one real decision (pinned §7).** What disciplines does the picker offer? Andy chose **"the athlete selects and weights all *potential* disciplines"** — the full distinct discipline set across every sport's bridge — over a sport-scoped list. All-or-nothing: non-zero weights must sum to 100, or the whole set clears (→ system defaults).

**Convention set.** `athlete_discipline_weighting.discipline_slug` stores the **canonical `discipline_id`** (`D-006`). There is no human discipline slug in `layer0.disciplines`, so storing the id makes the orchestrator unpack a direct remap with no slug→id mapping layer.

**Merge-conflict turn.** After X2 was green locally, the PR showed `mergeable_state: dirty` — and that was silently **blocking the GitHub Actions suite from running at all** (Actions don't run on a conflicted PR). Root cause: `#511`'s nutrition block was inserted at the same spot in `edit.html` (just after the Athlete-tab profile `</form>`). Both are independent additions under the Athlete tab → resolved by keeping **both** blocks. Full suite re-run green post-merge (2389).

---

## 3. File-by-file edits

### 3.1 `athlete_discipline_weighting_repo.py` (new, 103 lines)
- `load_discipline_catalog(db)` — all potential disciplines: `SELECT DISTINCT discipline_id, discipline_name FROM layer0.sport_discipline_bridge WHERE superseded_at IS NULL`, deduped by id, labeled via `discipline_display_name` (mirrors `routes/race_events.py`'s catalog pattern, minus the per-sport filter).
- `get_discipline_weighting(db, user_id)` → `{discipline_id: weight_pct}`.
- `replace_discipline_weighting(db, user_id, weights)` — all-or-nothing: filters zeros, validates non-empty set sums to exactly 100 and each ∈ 1..100 (raises `DisciplineWeightingError`), then `DELETE` + re-`INSERT`. Caller commits.
- `evict_layer1_on_discipline_weighting_change(db, user_id)` — mirrors `athlete_skill_toggles_repo.evict_layer1_on_skill_toggle_change` (weighting lives in the Layer 1 payload).

### 3.2 `routes/profile.py` (modified)
- GET `edit()`: loads `discipline_catalog` + `discipline_weighting`, passes to the template (next to the skill-toggle load).
- New `POST /profile/disciplines` (`save_disciplines`) — mirrors `save_skills`: parse `dw_<id>` fields → `replace_discipline_weighting` → commit → evict Layer 1 → flash → redirect to `?tab=athlete`. Validation failures flash + redirect without writing.

### 3.3 `templates/profile/edit.html` (modified)
- A **separate** `<form action="profile.save_disciplines">` in the Athlete tab (its own form so the sum-to-100 rule can't block the main profile save), placed after the profile form. Number inputs `dw_<id>`, a client-side running-total readout (`dw-total` / `dw-warn`), no inline `style=` (redesign §18 forbids it — uses the `hidden` attribute + JS toggle).
- Coexists with `#511`'s `{% if plan_nutrition %}` block (both kept at merge).

### 3.4 `layer4/orchestrator.py` (modified)
- `_athlete_discipline_overrides(layer1_payload)` — unpacks `training_history.discipline_weighting` → `{discipline_id: {"weight": float}}` (the 2A override shape; direct remap because `discipline_slug` == `discipline_id`).
- Threaded into **both** 2A call sites: the shared cone (plan_create/refresh/race-week) and `orchestrate_single_session`. Inert when empty (`{}` → 2A system defaults).

---

## 4. Code / tests

`tests/test_athlete_discipline_weighting_repo.py` (new, 141 lines, 10 tests, `_FakeConn` pattern from `test_layer4_cache.py`): catalog dedupe across sports; get round-trip + empty; `replace` valid-sum-100 / sum≠100-raises-writes-nothing / empty-clears-only / zero-filter / over-100-raises; orchestrator unpack shape (via `SimpleNamespace` + `DisciplineWeightRecord`).

**Suite: 2389 passed / 30 skipped** post-merge (full `tests/` + `etl/tests/`). CI green on `a284a6d` (Python suite + JS harness + Vercel).

---

## 5. Manual §5.0 verification steps

X2 is **inert until an athlete sets weights**, so the empirical proof is a deliberate set-and-observe (append to `CARRY_FORWARD.md` walkthrough ledger):

1. `/profile?tab=athlete` → "Discipline weighting" card lists all platform disciplines. Enter weights summing to 100 (e.g. MTB 45 / Trail Running 20 / Packrafting 20 / Climbing 15). Confirm running total reads 100 and "must equal 100" hint clears.
2. Save → "Discipline weighting saved." Reload → values persist.
3. Enter a set summing to ≠100 → save → flashes the sum error, **nothing written** (reload shows prior values).
4. Clear all boxes → save → reverts to system defaults (no rows).
5. Re-run a plan (or `/admin/plan/<id>/inspect`) and confirm `modality_group_allocations` / per-discipline `load_weight` reflect the athlete split where no race override exists (athlete > bridge precedence; race override is X3/X4).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — **X3 / X4 (the payoff slice)**

This is what actually fixes plan #61's TR-dominant AR allocation. X1a/X1b/X2 are scaffolding; X3/X4 makes race-derived discipline mix drive allocation.

**X3 — stop dropping race discipline mix at the 3B boundary.** The original diagnosis (`DisciplineMix_X1a_X1b` handoff) was `layer4/orchestrator.py:372-373` strips race terrain's per-row `discipline_id` + `pct_of_race`, so only `terrain_id` reaches Layer 3B. **Line numbers have moved** (orchestrator grew X1b.3b + X2 helpers since) — re-grep before editing:
```
grep -n "pct_of_race\|terrain_id\|discipline_id" layer4/orchestrator.py
```
Carry `discipline_id` + `pct_of_race` from `RaceTerrainEntry` (`layer4/context.py:290`) through into a `discipline_mix` structure rather than dropping them.

**X4 — precedence merge: race > athlete > bridge.** The seam is **already built** — X1b.2 added `race_discipline_overrides: dict[str, float] | None` to `q_layer2a_discipline_classifier_payload` (`layer2a/builder.py:739`, passed through at `:881`, default `None` = backwards-compatible). X4:
1. Derives a `{discipline_id: pct}` map from the race's terrain mix (X3's surfaced data).
2. Passes it as `race_discipline_overrides` at the 2A call sites (alongside the `athlete_discipline_overrides` X2 just wired).
3. Confirms precedence in `_apply_modality_group_pooling` / `_compute_load_weight`: **race override wins over athlete override wins over bridge default** (the `WeightResult.source` Literal already has `"race_override"` from X1b.2). Verify the pooling algorithm (spec §5.1, `Modality_Group_Spec_v1.md`) resolves the 3-way precedence correctly when all three are present.

**Coordinate with [#509](https://github.com/ahorn885/exercise/issues/509)** — "Layer 2A inclusion-precedence unification (race > athlete > curator default)", spun out of the Slice 1 session and explicitly **sequenced with X3/X4**. Same precedence theme on the *inclusion* axis (which disciplines are in) vs X4's *weight* axis (how much each). Read #509 before starting; they likely share a precedence helper.

**Win-condition proof:** re-run plan #61 (cold AR, Andy's race spec MTB ~45% / TR ~20%) and confirm the allocation is **MTB-dominant matching the race mix**, not TR-dominant. This is the whole reason for the 4-slice rewrite.

### 6.2 Alternative pivots
- Empirical validation of the now-shipped scaffolding before more building: `/admin/plan/64/inspect` (X1b.2 modality pooling — should show `foot` + `paddle_flatwater` groups, MTB-dominant from v1.5.0 bands); X1b.3a `craft_substitution_via_group` flag firing; X1b.3b alias-keyed substitution.
- Layer 0 Slice 2: `etl/migrations/layer0/` convention + first proof migration (owed from Slice 1, epic #488).

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — anchor sweep.
- **Start X3/X4 on a fresh branch off updated `main`.** This branch carried multiple slices and hit drift/conflicts twice; a clean base avoids the dirty-PR CI stall seen here.
- No Neon migration owed for X2 (table pre-existed). X3/X4 is orchestrator/Layer-2A logic — likely no DDL, but verify against `RaceTerrainEntry` availability.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Picker offers **all potential disciplines** (athlete selects + weights any subset), not a sport-scoped list | Andy | Athlete may train/race disciplines beyond their registered primary/secondary sports; the full set is the honest input surface. |
| 2 | All-or-nothing sum-to-100; empty clears to system defaults | Andy (carried from X1b spec §"all-or-nothing athlete weighting UI") | A partial split is ambiguous; either the athlete owns the whole mix or defers entirely to defaults. |
| 3 | `discipline_slug` column stores canonical `discipline_id` | Claude (no human slug exists; flagged, not silently chosen) | Makes the orchestrator unpack a direct remap, no mapping layer. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `athlete_discipline_weighting_repo.py` exists (103 lines) | ✅ wc |
| `tests/test_athlete_discipline_weighting_repo.py` exists (141 lines) | ✅ wc |
| `_athlete_discipline_overrides` in orchestrator | ✅ grep (3 hits) |
| `save_disciplines` + `load_discipline_catalog` in routes/profile.py | ✅ grep (4 hits) |
| `dw-form` / `discipline_catalog` in edit.html | ✅ grep (3 hits) |
| PR #514 merged to `main` | ✅ `a284a6d` in `git log origin/main` |
| Suite green | ✅ 2389 passed / 30 skipped + CI |

---

## 9. Files shipped this session

**Substantive (5 files — X2, PR #514):**
1. `athlete_discipline_weighting_repo.py` (new)
2. `routes/profile.py` (modified — GET load + `save_disciplines`)
3. `templates/profile/edit.html` (modified — weighting form)
4. `layer4/orchestrator.py` (modified — unpack + both 2A call sites)
5. `tests/test_athlete_discipline_weighting_repo.py` (new)

*(X1b.3b shipped earlier this session as PR #512 — separate substantive set, recorded there.)*

**Bookkeeping:**
6. `aidstation-sources/X2_AthleteDisciplineWeighting_v1.md` (design note)
7. `aidstation-sources/CARRY_FORWARD.md` (X2 status flip)
8. `aidstation-sources/CURRENT_STATE.md` (pointer → this handoff)
9. `aidstation-sources/handoffs/V5_Implementation_X2_AthleteDisciplineWeighting_2026_06_10_Closing_Handoff_v1.md` (this file)

---

**End of handoff.**
