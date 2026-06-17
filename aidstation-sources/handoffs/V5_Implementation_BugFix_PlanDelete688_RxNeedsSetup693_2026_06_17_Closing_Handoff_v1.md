# #688 / #693 — Plan-delete 500 fix + rx "needs setup" mislabel — Closing Handoff

**Session:** Andy logged a 15-note plan-71 feedback batch (→ issues #688–#694 + comments on #621/#283 + reopened #624) and asked to knock out as many as possible before a handoff. Triaged against the stop-and-ask triggers; shipped the two **trigger-free code bugs** (#688, #693). The rest are trigger-gated, blocked, or need prod logs (see §6).
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_UX_QuickWins_Wellness_526_527_Health_543_2026_06_17_Closing_Handoff_v1.md`
**Branch:** `claude/intelligent-darwin-aegp1o` (harness-pinned)
**Status:** both fixes committed (`506e22c`) on the branch; **1 PR, pending Andy auto-merge.** `Fixes #688, #693`.

---

## 1. Session-start verification (Rule #9)
Clone was stale at `bbecdd3` (PR #571, 2026-06-13); fast-forwarded the branch to `origin/main` `aa76aa8` (#543/#687) — 87 commits, no divergence (branch had not yet been worked). `verify-handoff.sh` not re-run (no prior-session file claims to reconcile on this branch). Working tree clean at start.

## 2. Session narrative
- Continuation of the issue-triage thread: the 15 plan-71 notes were already filed as #688–#694 (+ #621/#283 comments, #624 reopened) and #423/#205/#251 demoted to `priority:low`, #347 closed.
- Andy: "address those newest issues 1-15… see how many we can knock out before a handoff."
- Triage against CLAUDE.md triggers ruled most of the batch as needing Andy first (Trigger #1 prompt / #2 vocab) or blocked (#621) or needing a prod log (Rule #14). The two clean, surgical code bugs — **#688** (delete 500) and **#693** ("needs setup" mislabel) — were shippable without a trigger, so built both.

## 3. What shipped

### 3.1 #688 — deleting a generated plan 500'd (`routes/plan_create.py`)
`plan_create.delete_plan` (`/plans/v2/<id>/delete`, the route the plans-list "Delete" button hits for v2 `plan_versions` — `templates/plans/list.html:50,72`) nulls the known non-cascading back-references before the `DELETE` (`superseded_by_version_id` + the two `plan_refresh_log` audit pointers). It **missed** `plan_versions.refresh_parent_version_id` — a refresh child's pointer back to its parent, added later via `ALTER TABLE … ADD COLUMN … REFERENCES plan_versions(id)` (`init_db.py:2182`) with **no `ON DELETE`** clause (→ `NO ACTION`). So deleting a plan that had since been **refreshed** (a child version still points at it) tripped an FK violation → 500. Andy's 6/11 plan had been refreshed, hence the repro.
**Fix:** null `refresh_parent_version_id` for child rows pointing at this plan, alongside `superseded_by_version_id`; docstring updated to name it; **Rule #15** `print()` on successful delete.

### 3.2 #693 — rx "Current Rx" table mislabels prescribed exercises (`templates/rx/list.html`)
The Outcome column showed `needs setup` whenever `e.last_outcome` was empty. But every row in the **Current Rx** table *is* a `current_rx` (prescribed) row — a manually-edited / set-up exercise that simply hasn't been **logged** yet is not "needs setup." Added an `{% elif e.current_sets %}` branch → reads **`no log yet`** when a prescription exists; `needs setup` is reserved for a genuinely unconfigured row (no `current_sets`). One-line template branch; no route/data change.

## 4. Code/tests
- **`tests/test_routes_plan_create.py`** (`TestPlanLifecycleRoutes`): `test_delete_nulls_refresh_parent_back_reference` (the null-UPDATE fires, is `(plan, user)`-scoped, and **precedes** the `DELETE`) + `test_delete_missing_plan_skips_writes` (ownership miss → redirect, 0 commits, no DELETE).
- **`tests/test_redesign_rx_list_render.py`**: `test_rx_list_prescribed_but_unlogged_reads_no_log_yet` (prescribed + `last_outcome=None` → "no log yet", not "needs setup").
- **Full suite 2565 passed / 30 skipped** (+3). venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`. NO DDL; Layer-0 gate / JS harness unaffected.

## 5. Decisions pinned (this session)
| # | Decision | By |
|---|---|---|
| 1 | Ship only the trigger-free bugs (#688, #693); do **not** plow through Trigger #1/#2 items in the batch | Claude (per CLAUDE.md) |
| 2 | #688 diagnosed **statically** from the `init_db.py` FK graph (Neon egress blocked from the container — can't reproduce the 500 live) | Claude (Rule #14-aware) |
| 3 | #693 label = "no log yet" for prescribed-but-unlogged; keep "needs setup" only for no-prescription rows | Claude |
| 4 | Both fixes in one PR on the harness-pinned branch (vs the repo's usual one-issue-per-PR) — single pinned branch | Claude (harness constraint; flagged) |

## 6. Next session pointers — the rest of the 6/17 batch (triaged)

### 6.1 Needs Andy first (stop-and-ask triggers)
- **#694** — cull 5 mis-classified exercise-library entries (nasal-breathing climb, 1000 step-up, hanging leg raise in boots, weighted treadmill incline walk, high-rep strength endurance). **Trigger #2** — exercise-DB curation; needs ratification + a `layer0-apply` migration; confirm none gate/prescribe before culling (mirrors #644/#648).
- **#692** — spin / assault / stationary bike + cycling trainer look duplicative. **Trigger #2** vocab. First answer the empirical question (do they map differently to exercises?) then consolidate if not. (#586 already dropped `cycling_trainer` from `BIKE_TYPES`.)
- **#690** — strength-exercise variety vs. the high-variety coaching preference. Likely **Trigger #1** (synthesizer prompt) + confirm the preference reaches strength selection (overlaps #339/#304/#307).
- **#624 (reopened)** — discipline sessions resolve to home, not the nearest terrain venue (Cleburne/Chisenhall). #642 didn't fully fix it; the cardio/discipline route-locale assignment + nearby-venue discovery/terrain-tagging is the gap. Likely **Trigger #1/#3** — scope before building.

### 6.2 Code-actionable next (no trigger)
- **#691** — sled-drag prescribed with no sled: an equipment-gating gap in the 2C effective pool. Needs a trace of why the sled exercise's `equipment_required` isn't gating (could be data or the gate logic).
- **#689** — strength-substitution session shows two near-duplicate descriptions: clarify/de-dup the two render fields (rationale vs coach-note). Plan-view template/render.
- **#283** — uploaded sleep/FIT data still not on any `/wellness` graph. Needs the FIT field-decode trace (Rule #14: pull the prod `/admin/logs` decode line via the Vercel MCP, don't infer).

### 6.3 Blocked
- **#621** — surface supplement recommendations (daily/standard + per-workout, incl. home-page block): gated on **#218** (supplement de-stub) which is gated on **#253** (structured supplement capture) + a pregnancy field. Can't start the surface until the data exists.

### 6.4 Operating notes (read order — Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. This handoff 5. `./scripts/verify-handoff.sh`.

## 7. Manual verification — OWED (Andy-action)
Can't drive the live app / Neon from the container.
- **#688:** on prod, delete a plan that has been refreshed at least once → redirects with "Plan deleted", no 500. (The 6/11 plan is the original repro.)
- **#693:** `/rx` — a prescribed exercise with no logged outcome reads "no log yet" (not "needs setup"); a catalog/inventory exercise still reads "needs setup".
- (Carried) post-#572 live **T3 refresh** re-verify (Rule #14); #430 Slice C EX-id self-heal live-verify.

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `delete_plan` nulls `refresh_parent_version_id` before the DELETE | ✅ `routes/plan_create.py` (+ docstring + Rule #15 log) |
| rx Outcome cell reads "no log yet" for prescribed-unlogged rows | ✅ `templates/rx/list.html` (`{% elif e.current_sets %}`) |
| Tests added for both + full suite green | ✅ 2565 passed / 30 skipped |
| Commit on branch; PR opened with `Fixes #688, #693` | ✅ `506e22c` |
| CURRENT_STATE pointer updated | ✅ this entry |

## 9. Files shipped
**Substantive (2):** `routes/plan_create.py`, `templates/rx/list.html`. **Tests:** `tests/test_routes_plan_create.py`, `tests/test_redesign_rx_list_render.py`. **Bookkeeping:** `CURRENT_STATE.md`, this handoff, GitHub issues #688/#693.

## 10. Carry-forward
- Standing: post-#572 live **T3 refresh** re-verify (Rule #14).
- #430 Slice C: live-verify the EX-id self-heal on a real log + downstream plan-gen (Andy-action).
- The 6/17 batch remainder triaged in §6 — most need an Andy decision (Trigger #1/#2) before code.

---

**End of handoff.**
