# V5 Implementation — T-1.1+T-1.2: Persist Layer-4 Observations + Drop `shape_override` — Closing Handoff (2026-07-01)

**Session:** WS-1 T-1.1 (#418 part 1) + T-1.2 (dead `shape_override` removal), bundled as one PR per the execution plan's Global order §4.
**Date:** 2026-07-01
**Plan doc:** [`plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md) §3 WS-1 (T-1.1, T-1.2)
**Predecessor handoff:** [`V5_Implementation_PlanNaming_1056_T41_2026_07_01_Closing_Handoff_v1.md`](https://github.com/ahorn885/exercise/blob/main/aidstation-sources/handoffs/V5_Implementation_PlanNaming_1056_T41_2026_07_01_Closing_Handoff_v1.md)
**Branch:** `claude/plan-mode-nested-wadler-4h6bzf` · **PR:** [#1108](https://github.com/ahorn885/exercise/pull/1108), auto-merge armed (merge commit, Andy's go 2026-07-01)
**Status:** 12 substantive files (over the nominal 5-file ceiling, but the plan itself pre-scoped T-1.1+T-1.2 as "one PR" touching `payload.py` + all 8-10 `shape_override=None` construction sites + the migration + repo helper + 2 route files — see plan §3 WS-1 file lists). Suite: **4093 passed / 30 skipped, 0 failed** (one pre-existing fixture in `tests/test_redesign_admin_render.py` needed a new key added — see §3).

---

## 1. Session-start verification (Rule #9) — drift found and fixed

The prior handoff (`V5_Implementation_PlanNaming_1056_T41...`) pointed at a plan doc that **did not exist anywhere** — not on disk, not in git history (`git log --all` for the literal filename and for any file ever named `*wadler*`: zero hits).

| Claim | Anchor | Result |
|---|---|---|
| Plan doc `plans/going-to-plan-mode-nested-wadler.md` | file existence | ❌ MISSING — never committed |
| `scripts/verify-handoff.sh` anchor sweep | run it | Confirmed the ❌ automatically |
| T-4.1 code claims (migration, helper, callers, read sites, tests) | grep each anchor | ✅ all landed as claimed |
| PR #1104 | GitHub | ✅ **merged** (handoff said "not yet opened" — stale; a later commit had already fixed this) |

**Root cause, found via GitHub:** a follow-up session (same day) had already caught this exact gap and fixed it in commit `33832f3` ("Commit the T-4.1 project plan doc; fix dangling plan-doc references", PR #1105, merged) — it committed the plan under its real name, `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`, and repointed `CURRENT_STATE.md` + the T-4.1 handoff at it. My local checkout was simply **stale** (behind `origin/main` by several merges, including #1105). `git merge --ff-only origin/main` synced it; `verify-handoff.sh` then ran clean.

**Lesson for next session:** the plan doc name in this repo is `PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`, not `going-to-plan-mode-nested-wadler.md` (that string is a leftover local-branch/session-title artifact from when the plan was authored, never a real path — don't `git log` for it again).

---

## 2. What shipped

Executed exactly the plan's §3 WS-1 T-1.1 + T-1.2 tasks (see `plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md`), no scope drift.

### T-1.1 — Persist Layer-4 `notable_observations` (#418 part 1)

- **Migration** (`init_db.py`, end of `_PG_MIGRATIONS`): `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_observations JSONB` — nullable, auto-applies on next Vercel deploy (public schema, **no `layer0-apply` owed**).
- **Repo helpers** (`plan_sessions_repo.py`, new section after `load_hitl_gate`): `save_generation_observations(db, user_id, plan_version_id, observations)` (mirrors `save_hitl_gate`'s shape — one JSONB blob, caller owns the transaction) and `load_generation_observations(db, plan_version_id)` — **not** user-scoped, matching the existing `load_progress_blocks`/`load_plan_sessions_as_blocks` precedent (admin reads any user's plan).
- **Write site** (`routes/plan_create.py`, right after `persist_layer4_sessions(db, result)` in the ready-transaction): calls `save_generation_observations(db, uid, plan_version_id, result.notable_observations)` wrapped in `try/except` — best-effort, an observations-write fault cannot fail an otherwise-successful generation (Rule #15 `print()` on failure). Same transaction as the `ready` flip (no extra commit). This single call site covers **both** plan_create and plan_refresh — they share `_advance_plan_generation_locked`'s success path.
- **Read + render** (`routes/admin.py` `plan_inspect` / `templates/admin/plan_inspect.html`): new pure helper `_sort_observations_by_priority()` (mirrors the `_summarize_progress_blocks` "factor out for testability" precedent) puts `best_effort_plan`/`seam_unresolved` first, stable otherwise. New "Generation observations" card on the inspect page: category badge (red for the two priority categories), an `elevates_to_hitl` badge when set, the observation text, and evidence_basis.

### T-1.2 — Remove dead `shape_override` (bundled — same `Layer4Payload` model touch)

Confirmed dead first (`grep -rn "shape_override=" layer4/`): all **10** construction sites (plan doc said "8" — stale count, not a blocker) were hardcoded `shape_override=None`, and the only reader was its own now-removed validator.

- `layer4/payload.py`: deleted the `ShapeOverride` class (§7.8), the `shape_override: ShapeOverride | None = None` field on `Layer4Payload`, the `"shape_override"` member of `Observation.category`'s `Literal`, and the `_check_shape_override_observation` validator.
- Removed `shape_override=None,` from all 10 sites: `layer4/race_week_brief.py` (×2), `layer4/single_session.py` (×2), `layer4/plan_refresh.py` (×2), `layer4/plan_create.py` (×3), `layer4/per_phase.py` (×1).
- `layer4/__init__.py`: dropped `ShapeOverride` from the import + `__all__`.
- `tests/test_layer4_payload.py`: removed `test_shape_override_requires_observation` + `test_shape_override_with_observation_ok` + the `ShapeOverride` import.

**Not touched (out of scope for T-1.2):** `aidstation-sources/specs/Layer4_Spec.md` still references the old "escalate to next-run HITL gate" language — that's T-1.3 (spec-only, doc-only, separate task, not built this session).

---

## 3. Tests

- `tests/test_plan_sessions_repo.py` — new `TestGenerationObservations` (4 tests): save serializes to JSON, load returns `[]` on NULL/missing-row/missing-column, save-then-load round-trip.
- `tests/test_routes_plan_create.py` — 2 new tests on `_advance_plan_generation`: observations get persisted with the right `(uid, plan_version_id, observations)` via a monkeypatched `save_generation_observations`; a write-fault there does NOT block the `ready` flip.
- `tests/test_routes_admin.py` — new `TestSortObservationsByPriority` (3 tests): priority categories sort first, stable within each tier, empty-list passthrough.
- `tests/test_redesign_admin_render.py` — **required fixture fix, not new tests**: `_pv_ready_row()` (shared by 3 existing `plan_inspect` route-render tests) needed a `generation_observations` key added, since the fake `_PlanInspectConn` routes any `plan_versions` SELECT to the same canned row and my new read site fired a second, distinct SELECT against it.
- `tests/test_layer4_payload.py` — removed the 2 now-obsolete `shape_override` tests (see §2).
- Full suite after this session's changes: **4093 passed / 30 skipped**, 0 failed. (Did not separately re-measure the pre-session baseline count — the 4 new `TestGenerationObservations` + 2 new plan_create tests + 3 new admin tests − 2 removed shape_override tests is the net test-count delta from this diff alone.)

---

## 4. GitHub bookkeeping (done this session)

- **#1056 closed** (`completed`) — it was left open despite PR #1104 merging; fixed the tracker/reality mismatch, commented with the PR ref.
- **#418 commented + checklist updated** — checked off "surface `seam_unresolved`/`warning` observations somewhere an operator actually sees" (done, `/admin/plan/<id>/inspect`). Left OPEN: the "wire `elevates_to_hitl` into a HITL surface / drop the spec claim" item is T-1.3, not built this session.
- **New issue filed: [#1107](https://github.com/ahorn885/exercise/issues/1107)** — "Persist seam_reviews / validator_results on plan_versions (T-1.1 covered only notable_observations)". Per the plan's §5 bookkeeping note flagging this as a real gap T-1.1 doesn't close.
- **Not filed:** a separate "shape_override dead code" issue — the plan's §5 note suggested filing one, but the work is already done in this same PR; filing-then-immediately-resolving a backlog item is pure noise.

---

## 5. Next session pointers

Per the execution plan's §4 Global order, after T-1.1+T-1.2:

- **T-1.3** (doc-only, ungated, follow-on to T-1.1): update `specs/Layer4_Spec.md` §6.2/§8.7 to drop "escalate to next-run HITL gate" language. No code, no test — mechanically small.
- **T-1.4** (#930) — **GATE: Andy must ratify the one-sided taper anchor wording** in `layer4/week_seam_review.py`'s `SYSTEM_PROMPT` before this can build. Must land before T-1.5 (R3 ordering rule in the plan).
- **T-3.4** (#573) — ungated, no preconditions, independent of T-1.x: terrain-substitute backup strength on the refresh path.
- **WS-5** (integrations, T-5.1…T-5.7) — fully independent, no plan-gen coupling, can run in parallel with anything above.
- **WS-2 remains GATED** on Andy ratifying the render-vs-trim table (plan §3 WS-2 header) — do not start T-2.x without that.
- **Do NOT bump `LAYER4_PROMPT_REVISION`** ("20") until T-2.9 (single bump + one real-LLM walk, per plan R1).

### Operating notes (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `aidstation-sources/plans/PlanGenReliability_OrphanedData_PartialWiring_ExecutionPlan_v1.md` — the full execution plan (read §0 executor rules before touching any task)
6. `./scripts/verify-handoff.sh`

---

## 6. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `init_db.py` | `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_observations JSONB` at the end of `_PG_MIGRATIONS` |
| Repo helpers | `plan_sessions_repo.py` | `def save_generation_observations(db, user_id, plan_version_id, observations)` / `def load_generation_observations(db, plan_version_id)` |
| Write site | `routes/plan_create.py` | `save_generation_observations(db, uid, plan_version_id, result.notable_observations)` right after `persist_layer4_sessions(db, result)`, inside `try/except` |
| Admin read/render | `routes/admin.py` | `_sort_observations_by_priority` + `observations=` passed to `render_template` in `plan_inspect` |
| Template | `templates/admin/plan_inspect.html` | `{% if observations %}` "Generation observations" card |
| Dead code removed | `layer4/payload.py` | `grep -c shape_override layer4/payload.py` → 0 |
| Dead code removed | `layer4/__init__.py` | `ShapeOverride` absent from imports/`__all__` |
| Tests | `tests/test_plan_sessions_repo.py` | `class TestGenerationObservations` |
| Tests | `tests/test_routes_plan_create.py` | `test_generating_persists_generation_observations` / `test_generation_observations_write_failure_does_not_block_ready` |
| Tests | `tests/test_routes_admin.py` | `class TestSortObservationsByPriority` |
| Fixture fix | `tests/test_redesign_admin_render.py` | `_pv_ready_row()` includes `'generation_observations': None` |
| Suite | — | 4093 passed / 30 skipped |
| Neon | — | No `layer0-apply` owed — public-schema, auto-applies on deploy |
| GitHub | — | #1056 closed; #418 commented + checklist updated; #1107 filed |
| Branch | — | `claude/plan-mode-nested-wadler-4h6bzf`, pushed; PR [#1108](https://github.com/ahorn885/exercise/pull/1108), auto-merge armed (merge commit) |

**End of handoff.**
