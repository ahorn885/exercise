# #693 — rx "needs setup" mislabel (capacity/edited rows) — Closing Handoff

**Session:** Andy: "work on github issue 693." #693 was reopened/left-open after the 2026-06-17 partial fix (`{% elif e.current_sets %}` → "no log yet") because it only cleared the label for rows with a populated `current_sets`. Capacity records and manual edits that carry **only a weight or duration** (no sets) still fell through to **"needs setup."** Completed the fix at the right surface.
**Date:** 2026-06-20
**Predecessor handoff:** `V5_Implementation_767_ManualUpload_UnifiedUploadUI_Slice5_2026_06_20_Closing_Handoff_v1.md`
**Branch:** `claude/gracious-cerf-avzybf` (harness-pinned)
**Status:** committed on the branch; PR opened `Fixes #693`. Trigger-free surgical bug fix.

---

## 1. Diagnosis — the issue's hypothesized root cause was wrong

The issue guessed the page "still checks the old key (public `exercise_id`)" dropped in #430 Slice C. **It does not.** `routes/rx.py` (`/rx` = the "Exercises" page) was *already* name-keyed and **never referenced `exercise_id`** — it joins `current_rx` → `exercise_inventory` on `ei.exercise = cr.exercise`. So there was no stale-FK status check to repoint.

The real mechanism: **"needs setup" is a render-label decision in `templates/rx/list.html`, and it keyed off `current_sets` alone.** A "capacity record" in this system *is* a `current_rx` row with real loads (per #335: "user 1 has 117 `current_rx` rows, 18 weighted"). The per-user seed (`init_db._seed_current_rx_for_user`) stamps brand-new rows with `rx_source='Needs initial setup'` and **every dimension NULL**. Any logged session (`'From Training Log'`), manual edit (`'Manual override'`), or deload (`'Auto-deload'`) overwrites `rx_source` and fills ≥1 dimension. But the template asked only "is `current_sets` set?", so:

- a **manual edit** that set only a weight (e.g. a loaded carry — weight matters, sets left blank) → `current_weight` set, `current_sets` NULL → mislabeled **"needs setup."**
- a **capacity record** carrying only weight/duration (no sets) → same mislabel.

## 2. What shipped

### 2.1 `routes/rx.py`
- Added the seed sentinel `SEED_RX_SOURCE = 'Needs initial setup'` (the single value `init_db.py` stamps; comment cross-refs the seed) and `_RX_DIMENSIONS`.
- `_decorate_entry` now computes a per-row `needs_setup` flag: a row needs setup **iff** it is still a pristine seed — `rx_source` is the seed sentinel (or NULL) **and** none of `current_sets/current_reps/current_weight/current_duration` is populated. Captures all three issue cases (capacity record / manual edit / touched `current_rx`).

### 2.2 `templates/rx/list.html`
- The Outcome cell now branches on `e.needs_setup` (reserve "needs setup") with the fall-through reading "no log yet". Order: `last_outcome` → outcome chip; else `needs_setup` → "needs setup"; else → "no log yet".

## 3. Tests (`tests/test_redesign_rx_list_render.py`)
- **`test_rx_list_capacity_without_sets_is_not_needs_setup`** — the regression test: a `Manual override` row with `current_weight` set but `current_sets=None` renders **"no log yet"**, not "needs setup". (Fails on the old `current_sets`-only template.)
- **`test_rx_list_pristine_seed_reads_needs_setup`** — a seed row (`rx_source='Needs initial setup'`, all dimensions NULL) still reads "needs setup".
- Existing `test_rx_list_prescribed_but_unlogged_reads_no_log_yet` (has `current_sets`) unchanged and green.
- **Full suite 2832 passed / 30 skipped** (venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`). No DDL / no cache / no prompt / no cross-layer contract change.

## 4. Decisions pinned
| # | Decision | By |
|---|---|---|
| 1 | Fix at the render label (`needs_setup` derived in the route), not a data migration — `/rx` was already name-keyed; the issue's `exercise_id`-FK hypothesis didn't match the code | Claude (flagged the discrepancy) |
| 2 | "Needs setup" ⟺ pristine seed (`rx_source` sentinel **and** no dimension), not `current_sets` presence | Claude |
| 3 | No cross-row layer0-EX-id aggregation (a logged-but-differently-named sibling row reading capacity for the seed row) — speculative; that name-unification case is owned by #679/#335, and Andy's live data logs in-place against the bare seed names | Claude |

## 5. Scope checklist (issue #693)
- [x] "Needs setup" clears once an exercise has a capacity record / manual edit / `current_rx`.
- [x] Point the status check at the right surface — corrected: the page was already off the dropped public FK; the bug was the `current_sets`-only label, now keyed off the seed sentinel + capacity dimensions.

## 6. Manual verification — OWED (Andy-action)
Can't drive the live app from the container. On prod `/rx`: an exercise you manually edited to a weight (sets left blank), or a capacity row with only a weight/duration, reads **"no log yet"** (or its outcome chip), not "needs setup"; a brand-new never-touched seed row still reads "needs setup".

## 7. Operating notes for next session (Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. This handoff 5. `./scripts/verify-handoff.sh`.

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `SEED_RX_SOURCE = 'Needs initial setup'` + `needs_setup` computed in `_decorate_entry` | ✅ `routes/rx.py` |
| Outcome cell branches on `e.needs_setup` (fall-through = "no log yet") | ✅ `templates/rx/list.html` |
| Regression test (weight-only, no sets → "no log yet") + seed test added | ✅ `tests/test_redesign_rx_list_render.py` |
| Full suite green | ✅ 2832 passed / 30 skipped |
| Commit on branch; PR `Fixes #693` | ✅ |
| CURRENT_STATE pointer updated | ✅ this entry |

## 9. Files shipped
**Substantive (3):** `routes/rx.py`, `templates/rx/list.html`, `tests/test_redesign_rx_list_render.py`. **Bookkeeping:** `CURRENT_STATE.md`, this handoff, issue #693 comment.

## 10. Carry-forward
- No new carry items. Standing #430 Slice C / #679 EX-id self-heal live-verify is unrelated to this label fix.

---

**End of handoff.**
