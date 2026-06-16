# Strength Rx render slice + drain-visible logging (#335) — Closing Handoff

**Session:** Reopened #335 ("strength loads not keyed off capacity records"); root-caused against live prod, shipped the bounded render + observability slice, deferred the real fix.
**Date:** 2026-06-16
**Predecessor handoff:** `V5_Implementation_plan72_TaperWeekPlaceableDays_EnvVarDuping_2026_06_16_Closing_Handoff_v1.md`
**Branch:** `claude/hopeful-pasteur-b8saw4` (render slice, merged via PR #662) → `claude/rx-wire-335-bookkeeping` (this handoff + docs)
**Status:** 2 substantive files (under ceiling). PR #662 MERGED. #335 stays OPEN for the deferred arc.

---

## 1. Session-start verification (Rule #9)

The predecessor (plan-72, PR #661) had no §8 anchor table (4-section closing note); I spot-checked its five claims directly:

| Claim | Anchor | Result |
|---|---|---|
| `placeable_days_in_week()` helper | `layer4/session_grid.py:409` | ✅ grep |
| cutoff wire + Rule-#15 log | `layer4/per_phase.py:1085` `placeable_days:` | ✅ grep |
| re-export | `layer4/__init__.py:429` | ✅ grep |
| tests | `tests/test_layer4_session_grid.py:531` `TestPlaceableDaysInWeek` | ✅ grep |
| DB env-var doc | `DATABASE.md:89` | ✅ grep |

**Reconciliation note:** clean — all plan-72 claims landed; working tree clean on the pinned branch.

---

## 2. Session narrative

- Andy: "check it out and lets keep working" pointing at the plan-72 closing handoff. Plan-72 was fully shipped/merged; its owed items were non-buildable-now (ops/doc nits + watch-next-plan-gen).
- Offered next-focus options via `AskUserQuestion` → Andy chose **#335** (strength sessions render as bare labels — reopened 2026-06-15 from the pv=71 read).
- **Diagnosis (Rule #14, read-only `neon-query` against prod):**
  - Capacity records exist + reach Layer 4: user 1 has 117 `current_rx` rows, 18 weighted.
  - Names matched only on a substring grep illusion (`Back Squat` is a prefix of `Back Squat (Barbell)`); the actual layer0 0B names carry equipment qualifiers, the `current_rx` rows are bare → exact-match lookup always misses.
  - Decisive artifact: pv=71's persisted `plan_sessions` strength rows are **100% `first_exposure` (32/32)**, including `Back Squat (Barbell)` / `Bulgarian Split Squat (DB)` (Andy has weights for the bare names).
  - The hit/miss summary was a silent `logging.info` (no `basicConfig` → no handler) — why it was never noticed.
- Two `AskUserQuestion` rounds on the fix: Andy rejected the alias/normalization bridge ("a single source of truth for these values, not matching two different sets of names") and flagged the load-display as "a much bigger issue … take the baseline, consider it, issue a progression … we designed all sorts of logic for this" (= the rx_engine `next_*` machinery + Phase 2b). Decision: **ship the render fixes now, defer the source-of-truth + progression arc.**
- Shipped PR #662 (auto-merge, squash); merged green. Issue #335 commented + left OPEN.

---

## 3. File-by-file edits

### 3.1 `layer4/rx_wire.py` (modified)

- `_render_current_rx` (anchor `layer4/rx_wire.py:170`) now returns a **load-only** string (`"185 lb"` / `"45s"`) instead of `"{sets} × {reps} @ {weight}"`. `view.html` prepends `sets × reps @`, so the old full string double-rendered (`3 × 5 @ 3 × 5 @ 185 lb`). Docstring carries a NOTE pointing the sets/reps + `next_*` progression reconciliation at the deferred #335 arc.
- Decision summary (`print("rx_wire: hits=… first_exposure=… skipped=…")`) and the per-exercise lookup-failure line converted from `logging` to `print()` (Rule #14/#15 — reaches the Vercel drain → `/admin/logs`). Removed the now-orphaned `import logging` + `_log` module logger.
- Stale docstring example in `apply_current_rx` updated to the load-only form.

### 3.2 `tests/test_layer4_rx_wire.py` (modified)

- Three `TestCurrentRxHit` assertions updated to the load-only contract: `"185 lb"`, `"187 lb"`, `"45s"` (were `"3 × 5 @ 185 lb"`, etc.). Added a one-line comment explaining the template-prefix contract.

---

## 4. Code / tests

No net test count change (3 assertions edited in place). `tests/test_redesign_view_plan_render.py:231` (`'4 × 5 @ 75% 1RM'`) is the LLM-free-text path and already validates the load-only template contract — left as-is. Verification: `pytest tests/ -k "layer4 or rx_wire or view_plan or plan_create"` → **1218 passed, 5 skipped**.

---

## 5. Manual §5.0 verification steps

None gating. (Optional, once the deferred fix lands: confirm a fresh plan renders a capacity-keyed load for a logged lift instead of `first_exposure`.)

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Spec the #335 real fix — single source of truth + progression.** Per Andy: no alias bridge. Write a design doc covering (a) migrating `current_rx`/`training_log` onto `layer0.exercises` (Catalog Migration Plan #430 Phase 3–5 end-state, retiring `public.exercise_inventory` as the strength name authority), and (b) surfacing `current_rx.next_*` (the rx_engine already computes the progression) reconciled with the per-phase dose policy. Cross-layer + a real data migration → spec-first, Andy sign-off before code, likely sliced across sessions. This is a Stop-and-ask #3 (cross-layer) area.

### 6.2 Alternative pivots

- #423 — synthesizer wastes ~418s extended-thinking before the forced retry (high-prio latency bug, Trigger #1).
- #592 / #593 — event-windows race terrain/weather + reduced-volume travel days.
- #427/#428/#429 — determinism epic.

### 6.3 Operating notes for next session

1. `CLAUDE.md` — stable rules (Rule #13).
2. `CURRENT_STATE.md` — what just shipped + current focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Ship render + logging fixes now; defer the substantive fix | Andy | Bounded, low-risk; the real fix is a multi-session arc |
| 2 | No alias/normalization bridge — a single source of truth for exercise names/values | Andy | Matching two name-sets is the wrong long-term shape |
| 3 | Prescription = baseline considered + progressed (`next_*`), not raw baseline echo | Andy | "issue an appropriate exercise to help them progress" |
| 4 | `_render_current_rx` returns load-only (template owns `sets × reps @`) | Claude | Consistent with LLM-free-text + first-exposure paths; kills the double-render |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/rx_wire.py` `_render_current_rx` returns load-only (no `× … @` in the weight/duration branch) | ✅ inspection |
| `print("rx_wire: hits=` present; `import logging` absent in rx_wire.py | ✅ grep |
| `tests/test_layer4_rx_wire.py` asserts `== "185 lb"` / `"187 lb"` / `"45s"` | ✅ grep |
| PR #662 merged to `main` (commit `d56440e`) | ✅ git log |
| #335 commented + left OPEN | ✅ issue comment 4722909853 |
| `CURRENT_STATE.md` last-shipped = #335 render slice | ✅ inspection |

---

## 9. Files shipped this session

**Substantive (2 files):**
1. `layer4/rx_wire.py`
2. `tests/test_layer4_rx_wire.py`

**Bookkeeping:**
3. `aidstation-sources/CURRENT_STATE.md`
4. `aidstation-sources/handoffs/V5_Implementation_RxWire_RenderSlice_335_2026_06_16_Closing_Handoff_v1.md` (this file)
5. GitHub: #335 comment (root cause + render slice shipped + deferred arc; issue stays open)

---

## 10. Carry-forward updates

None this session (no new walkthrough scenarios or doc nits beyond the deferred #335 arc, which is tracked on the issue + CURRENT_STATE NEXT).

---

**End of handoff.**
