# V5 — Layer 3C Item B: surface informational gate items as plan-home coaching notes (closing)

**Date:** 2026-06-23 · **Branch:** `claude/awesome-ride-5j0m3k` · **Commit:** `f6deab7` · **PR:** not yet opened — work pushed, awaiting Andy's "open it" (§6.3 PR-gated model). **Epic:** #211 (Layer 3 gate). **Continues:** the `V5_Layer3C_ConflictDetection_NextSteps_211_2026_06_23_Kickoff_Handoff_v1.md` forward map — this is **Item B**, the kickoff's named "best first build."

---

## 1. What shipped

The kickoff handoff's **Item B** — *surface informational flags on green plans as plan-page coaching notes.*

**The gap.** Layer 3C Slice 2 (#911) made `informational` gate items **display-only** (`compute_gate_status` never parks a plan on them) and surfaces the upstream advisory `coaching_flags` (2A–2E) + any 3B `informational` note as such items. But the only render surface for them was the **review screen**, which appears *only when something else parks the plan*. A fully-green plan — the common case — therefore **never showed its informational items**; they sat in the persisted gate record unseen.

**The fix (additive, no contract change).** The plan home (`plan_create.view_plan` → `templates/plan_create/view.html`) now lists them as **coaching notes**:

- **`routes/plan_create.py` — new `_plan_coaching_notes(db, uid, plan_version_id) -> list`** (next to the other gate-display helpers, after `_build_revise_urls`). Loads the persisted gate via `load_hitl_gate` and returns its `severity == "informational"` items. **Advisory/fail-safe** — a gate load/parse fault prints a Rule #15 line and degrades to `[]`, never 500s the view (mirrors the nutrition/conditions/evidence loads in the same route). `view_plan` calls it and passes `coaching_notes=` to the template.
- **`templates/plan_create/view.html`** — a `card card-pad sec` panel after the #826 science panel, headed `● Coaching notes`, rendering each note's `.message` (coaching voice: "Context we flagged while building this plan — none of it blocked it. Worth knowing as you train so you can see where the edges are."). Wrapped in `{% if coaching_notes %}` so a clean plan with zero informational items shows no panel.

**Scope is exactly the display-only set** — `severity == "informational"`, which is both the 3C-surfaced `coaching_flags` *and* any 3B informational note (the same set `compute_gate_status` excludes from the verdict). Warnings/blockers never render here — they belong on the review screen, and on a generated (ready) plan they were already resolved. No `GateItem`/`Layer3DGate` contract change, no schema/migration/cache/prompt change, no orchestrator change. The gate is already persisted unconditionally for green plans (`orchestrator.py:1838`, before the park/raise), so the data was already there.

---

## 2. Files touched (4 substantive + bookkeeping)

| File | Change | Anchor (Rule #9 check) |
|---|---|---|
| `routes/plan_create.py` | `_plan_coaching_notes` helper + `coaching_notes=` in the `view_plan` render | `grep -n "def _plan_coaching_notes\|coaching_notes=" routes/plan_create.py` |
| `templates/plan_create/view.html` | `● Coaching notes` panel after the science panel | `grep -n "Coaching notes\|coaching_notes" templates/plan_create/view.html` |
| `tests/test_layer3d_wiring.py` | `_informational_item` builder; `TestPlanCoachingNotes` (×4) + `TestCoachingNotesRender` (×2) | `grep -n "def _informational_item\|class TestPlanCoachingNotes\|class TestCoachingNotesRender" tests/test_layer3d_wiring.py` |
| `specs/Layer3D_Spec.md` | §5.4 record + §11 "Green-plan coaching notes" + §9 edge row + §13 split (Item B shipped / promotion still future) + TS-3C-10 | `grep -n "Green-plan coaching notes\|Item B\|TS-3C-10" aidstation-sources/specs/Layer3D_Spec.md` |
| `CURRENT_STATE.md` / `CARRY_FORWARD.md` | rolling-pointer + carry update (this session) | bookkeeping |

---

## 3. Tests

- `tests/test_layer3d_wiring.py` **+6**:
  - `TestPlanCoachingNotes` — returns informational items only (warnings/blockers excluded); `None` gate → `[]`; no-informational → `[]`; load-failure degrades to `[]` and prints the Rule #15 line (`capsys`).
  - `TestCoachingNotesRender` — renders the **real** `view.html` (stub `base.html` + `FileSystemLoader`, the `test_plan_view_conditions_render` pattern): the informational messages appear under "Coaching notes"; an empty list renders **no** panel.
- **Full suite `tests/ etl/tests/` → 3633 passed / 30 skipped** (container venv; `DATABASE_URL` dead-localhost). The 3 `Layer3BEvidenceBasisWarning` warnings pre-exist (#217). **ruff clean** on `routes/plan_create.py` + `tests/test_layer3d_wiring.py`.
- **LIVE-VERIFY (Andy-owed, optional — container can't run plan-gen):** on a generated green plan that carried ≥1 informational flag (e.g. a discipline gear-gated at a locale, or a 2E low-calorie advisory), confirm the **Coaching notes** panel renders the message(s). Low-risk — the template binding is render-test-covered; this is the visual proof only.

---

## 4. Open / next (the kickoff forward map, updated)

3C's node is functionally complete and Item B closes the surfacing story. Remaining items from the kickoff §2 map, in 4-tier order:

- **Item D — #213 live-verify walk** (tier-2, Andy-owed): the `[Fix this]` revise-links + staleness re-kick walk. Still the one shipped-but-unverified gate function. Orthogonal to 3C code.
- **Item A — flag → `warning` promotions** (signal-gated): flip a §7.1 ★ flag_type (`unbridgeable_terrain`, `low_calorie_target_relative_to_rmr`) into `_FLAG_WARNING` **only when prod shows a real informational miss.** One-line edit (kickoff §5). Don't guess.
- **Item C — CN-3+ new detectors** (STOP-AND-ASK, Trigger #5 + spec-first): don't build speculatively. Kickoff §4 holds the candidate set + the bar. No prod signal that CN-1/CN-2 miss a real class yet.

**Gut check (carried from the kickoff, still true).** 3C may be done for v1. Item B was the last *buildable, non-gated* increment; A waits on data, C waits on a real miss, D is Andy's hands. The honest next move after this is **not more 3C** — it's whatever the 4-tier order surfaces across the open epics (or D, to close the gate epic cleanly).

---

## 5. Operating notes (§6.3 — next-session read order, Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + focus
3. `CARRY_FORWARD.md` — rolling cross-session items
4. This handoff (+ the `…Layer3C_ConflictDetection_NextSteps…` kickoff it continues)
5. `./scripts/verify-handoff.sh` — anchor sweep

**PR-gated (Andy 2026-06-19):** work is committed + pushed to `claude/awesome-ride-5j0m3k`; bookkeeping rides the same branch. **Do not open the PR until Andy says so.** When he does: push (if needed), open ready-not-draft, `enable_pr_auto_merge`, and — per the #911 lesson — **CI may need a manual `ci.yml` `workflow_dispatch`** on the branch ref (web-flow PRs don't always auto-fire `on: pull_request`), else auto-merge hangs waiting on the required checks (`Python unit suite (stubbed)` / `JS harness (jsdom)` / `Layer 0 integrity gate`). Re-check #211 + `list_pull_requests` right before opening (parallel-build lesson; clean as of this session — 0 open PRs).

---

## 6. Recurring lessons applied

- **Route-ref drift (#897 lesson).** Verified the render surface against on-disk code before wiring: the plan home is `plan_create.view_plan` → `plan_create/view.html` (the v2 path; `plans.view_plan` is the v1 `training_plans` view, not this), the gate loads via `load_hitl_gate`, and green gates persist their items (`orchestrator.py:1838` runs before the park/raise). No assumptions taken from the handoff narrative.
- **Cross-source de-dup is already done upstream** — the informational set is produced by `surface_orphaned_flags` with its CN/2D suppression; Item B is a pure read of that persisted set, so no new suppression logic.

---

## 7. Gut check

- **Risk:** the surfaced flag `message` strings come verbatim from the 2A–2E builders; a poorly-worded one will read awkwardly as a coaching note. That's an upstream copy fix (the source builder), not an Item-B fix — the kickoff flagged this. Nothing here transforms the message.
- **What might be missing:** no per-note "Fix this" link (the review screen has them via `_build_revise_urls`). Deliberately omitted — Item B is "list them as notes" (kickoff §5), and these are FYI on an already-built plan; adding the link is a clean follow-up if Andy wants it, not a v1 need.
- **Best argument against:** if 3C is truly done-for-v1, even Item B is optional polish. Counter: it closes a real, visible gap (a green plan silently hiding context it computed), it's the kickoff's explicit "best first build," and it's additive + fail-safe + test-covered with zero contract surface — the cheapest possible way to complete the surfacing story.

---

## 8. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Helper | `routes/plan_create.py` | `def _plan_coaching_notes(` returns `[it for it in gate.items if it.severity == "informational"]`; fail-safe `except` prints `_plan_coaching_notes: gate load failed`; `view_plan` passes `coaching_notes=` (grep) |
| Template | `templates/plan_create/view.html` | `● Coaching notes` panel guarded by `{% if coaching_notes %}`, loops `note.message` (grep — 1 panel, after the `_science_panel.html` include) |
| Tests | `tests/test_layer3d_wiring.py` | `class TestPlanCoachingNotes` (×4) + `class TestCoachingNotesRender` (×2) + `def _informational_item`; full suite `… pytest tests/ etl/tests/` → 3633 passed / 30 skipped |
| Spec | `specs/Layer3D_Spec.md` | `### 11` "Green-plan coaching notes (Item B" paragraph; §5.4 record; §13 Item-B-shipped split; `TS-3C-10` row (grep) |
| Issue | #211 | comment: Item B (green-plan coaching notes) shipped on `claude/awesome-ride-5j0m3k` (`f6deab7`); 3C surfacing story complete; epic stays OPEN (Items A/C/D remain per kickoff §2) |
