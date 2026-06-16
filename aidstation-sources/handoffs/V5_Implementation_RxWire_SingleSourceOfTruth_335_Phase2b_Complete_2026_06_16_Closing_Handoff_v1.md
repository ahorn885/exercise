# Strength Rx single source of truth (#335 Phase 2b) — COMPLETE — Closing Handoff

**Session:** Continued the #335 Phase-2b arc from its predecessor handoff and **finished both remaining pieces** — (A) the 4 new layer0 exercises + backfill, (B) the `rx_wire` EX-id surface fix + phase-aware %1RM load. The single-source-of-truth fix is now end-to-end: a logged baseline resolves by the layer0 EX-id and renders as a phase-appropriate load.
**Date:** 2026-06-16
**Predecessor handoff:** `V5_Implementation_RxWire_SingleSourceOfTruth_335_Phase2b_2026_06_16_Closing_Handoff_v1.md`
**Branch:** `claude/rxwire-single-source-truth-dfcrfc` (both PRs merged from it).
**Status:** PRs #670 + #671 MERGED. `0011` APPLIED to prod. #335 Phase-2b implementation COMPLETE; **live verification of a fresh plan is owed** (Andy-action — can't trigger plan-gen from the container).

---

## 1. Session-start verification (Rule #9)
`./scripts/verify-handoff.sh` clean at start — all predecessor §8 anchors present, working tree clean, on-branch. Spot-checked the on-disk state of `rx_engine.current_rx_by_layer0_id`, the `current_rx.layer0_exercise_id` ALTER, the crosswalk, and the 16-name backfill — all matched. No drift. Direct continuation.

## 2. Session narrative
- Andy "check it out and let's keep going" → read the predecessor handoff; the two remaining pieces were precisely specified there. Chose order via `AskUserQuestion`: **"do a then b."**
- **(A)** Trigger #2 gate: authored the per-entry 0B specs for the 4 new exercises and got Andy's per-entry sign-off via `AskUserQuestion`. Three judgment calls resolved: Curl → `Pull-H` (matching the EX234 Hammer Curl precedent, over the handoff's "Various" guess); Sit-Up → `Anti-Extension` (catalog ab convention, no new "flexion" vocab); KB Halo → Andy corrected the framing to a **strength + stability** exercise (not a warm-up) → `{Rotation, Anti-Extension}` → rx Rotation.
- **(B)** Implemented the EX-id-first lookup + the phase-aware %1RM model. Chose **Epley + its inverse** for D5b (self-consistent with the est-1RM already in `calculations`, no separate table to cite/maintain; the implied rep-% matches D5b's anchors).

## 3. File-by-file (shipped this session)
- **`etl/migrations/layer0/0011_add_strength_rx_exercises.sql`** (#670) — adds EX246 Barbell Row (Bent-Over), EX247 Biceps Curl (DB), EX248 Sit-Up, EX249 Kettlebell Halo — full 0B fields + 26 `sport_exercise_map` rows — at `0B-v1.6.12`. Pure additions, idempotent (NOT-EXISTS guards), atomic verify block (4 active + 26 map rows + 0 dangling refs). No public-schema DDL, no `LAYER4_PROMPT_REVISION` bump.
- **`init_db.py` `_PG_MIGRATIONS`** (#670) — 4 name-keyed backfill UPDATEs: `Row`/`Curl`/`Sit Up`/`KB Halo` → EX246–EX249 (completes the #667 map). Comment at the block head updated from "deferred" to "now map to EX246–EX249".
- **`layer4/rx_wire.py`** (#671) — (B1) `apply_current_rx` looks up `current_rx_by_layer0_id(ex.exercise_id)` first, name fallback only for un-backfilled rows; `print` summary now splits `id=`/`name=` hits (Rule #15). (B2) `_render_current_rx(rx, target_reps, unit_pref)` computes the phase-aware load; new helpers `_parse_target_reps` (int / "8-12" midpoint / non-numeric→None) and `_round_to_gym_increment` (5 lb / 2.5 kg). Module docstring rewritten (Track-3 dependency note replaced by the EX-id + load-model description).
- **`tests/test_layer4_rx_wire.py`** (#671) — new `TestEXIdLookup`, `TestPhaseAwareLoad`, `TestRepsAndRounding`; the two #469 weight tests realigned to phase-aware behavior (one repurposed to cover the non-numeric-reps fallback's whole-lb display).

## 4. Code/tests
All green: rx_wire 34, Layer-4/plan/render suites 1510 passed / 5 skipped, etl/tests 90, rx/progression 18. Migration validated locally on PG16 (baseline + 0006–0011 apply clean + idempotent; `validate_layer0` PASS, `exercises_fk` 0 violations).

## 5. Manual verification — OWED (Andy-action)
The visible #335 win renders only on a **freshly generated/refreshed plan** (rx_wire is post-synthesis; it re-runs at gen time, so existing persisted `plan_sessions` don't retroactively change). **Owed:** generate/refresh a plan for Andy and confirm via read-only `neon-query` on `plan_sessions` that the backfilled lifts (Back Squat, …, and the 4 new ones once logged) render capacity-derived loads, **not** `first_exposure`. Expect the `rx_wire: hits=N (id=… name=…)` line in `/admin/logs` to show non-zero `id=` hits.

## 6. Next session pointers

### 6.1 REMAINING / FOLLOW-UPS
- **Verify the win on a fresh plan** (above) — then **CLOSE #335** if it renders capacity-derived loads. Left OPEN pending that live check.
- **Slice C (the rest of #430):** retire `public.exercise_inventory` route-by-route (references/injuries/training/plans/purchases/coaching) — a separate, non-gating track. `rx_engine.apply_session_outcome` still reads `exercise_inventory` by name for static fields (`movement_pattern`, `weight_increment`); migrating the WRITE path to EX-ids + layer0 `movement_patterns` (via the `layer0_progression` crosswalk already shipped) is the natural next slice. Not started.
- **`weight_increment` (D4):** the phase-aware model sidesteps the per-exercise increment for the rendered load, but `apply_session_outcome`'s progression still uses it. No action needed for #335; note for Slice C.

### 6.2 Alternative pivots
#423 (synth thinking-budget latency, high-prio), #592/#593 event-windows, #427/#428/#429 determinism epic.

### 6.3 Operating notes for next session
1. `CLAUDE.md` (Rule #13). 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md`. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned (this session)
| # | Decision | Picked by |
|---|---|---|
| 1 | Order: do (A) the 4 exercises, then (B) the surface fix | Andy |
| 2 | Biceps Curl → `Pull-H` (matches EX234), not "Various" | Andy |
| 3 | Sit-Up → `Anti-Extension` (catalog ab convention; no new vocab) | Andy |
| 4 | KB Halo = strength+stability → `{Rotation, Anti-Extension}` → rx Rotation | Andy |
| 5 | D5b load model = Epley + Epley-inverse (no separate %1RM table) | Claude |

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `0011_add_strength_rx_exercises.sql` present (EX246–EX249 + map) | ✅ etl/migrations/layer0/ |
| 4 backfill UPDATEs (`Row`/`Curl`/`Sit Up`/`KB Halo`→EX246–249) in `_PG_MIGRATIONS` | ✅ init_db.py |
| `rx_wire.apply_current_rx` calls `current_rx_by_layer0_id` first | ✅ layer4/rx_wire.py |
| `_render_current_rx` phase-aware (`calculate_1rm` + Epley inverse) | ✅ layer4/rx_wire.py |
| PRs #670 + #671 merged to `main` | ✅ |
| `0011` applied to prod via `layer0-apply` | ✅ run 27649158745 success |
| `CURRENT_STATE.md` last-shipped = #335 Phase-2b COMPLETE | ✅ |

## 9. Files shipped
**Substantive:** `0011_add_strength_rx_exercises.sql`, `init_db.py`, `layer4/rx_wire.py` (+ test) — across 2 PRs (each ≤5 files).
**Bookkeeping:** design-doc status flip, `CURRENT_STATE.md`, this handoff, #335 issue comment.

## 10. Carry-forward
The fresh-plan live verification (§5) is the one owed item from this arc. Plus the standing pre-existing carry: the post-#572 live **T3 *refresh*** re-verify (Rule #14).

---

**End of handoff.**
