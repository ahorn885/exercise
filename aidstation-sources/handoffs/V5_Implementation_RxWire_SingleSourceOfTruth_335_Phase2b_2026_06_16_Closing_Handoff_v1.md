# Strength Rx single source of truth (#335 Phase 2b) — Closing Handoff

**Session:** Continued #335 from the render slice into the signed-off Phase-2b arc — keyed the strength-rx path off the layer0 EX-id (single source of truth), shipped crosswalk + column + backfill. Remaining: 4 new layer0 exercises (Trigger #2) + the %1RM surface PR.
**Date:** 2026-06-16
**Predecessor handoff:** `V5_Implementation_RxWire_RenderSlice_335_2026_06_16_Closing_Handoff_v1.md`
**Branches (all merged):** `claude/hopeful-pasteur-b8saw4` (#662/#663), `claude/strength-sot-335-*` (#664 design, #665 crosswalk, #666 column, #667 backfill).
**Status:** 6 PRs merged. #335 OPEN for the remaining 2 pieces below.

---

## 1. Session-start verification (Rule #9)
Clean — the render slice (#662) claims were verified at the start of this session; this is a direct continuation. No drift.

## 2. Session narrative
- Andy "keep going" → designed the substantive #335 fix. Locked decisions via `AskUserQuestion`: **phase-aware %1RM** load model · **identity + load model in one arc (split PRs)** · **backfill history to EX-ids** · **single source of truth, NOT an alias bridge**.
- Key insight: the synthesizer already emits the **layer0 EX-id** on `StrengthExercise.exercise_id`, so keying `current_rx` off the EX-id (not the name) is the single source of truth and dissolves the `Back Squat (Barbell)` vs `Back Squat` mismatch.
- Grounded against prod: `layer0.exercises` has `exercise_id`, `exercise_name`, `movement_patterns[]` (20-value biomechanical taxonomy, multi-valued), its own `progression_exercise_id`/`regression_exercise_id` graph, **no `weight_increment`, no single progression `movement_pattern`**. The v1 rx `PROGRESSION_RULES` keys off a single pattern → needs a crosswalk.
- Pulled Andy's 117 `current_rx` names + the 201 active layer0 exercises; rapidfuzz + **Andy HITL review** produced the 16-name backfill map. 4 names (Row/Curl/Sit Up/KB Halo) need NEW layer0 exercises (Andy: "need a new value").

## 3. File-by-file (shipped this arc)
- **`aidstation-sources/designs/Layer4_StrengthRxSingleSourceOfTruth_335_Phase2b_Design_v1.md`** (#664) — the design + locked decisions (D1–D7).
- **`layer0_progression.py`** + `tests/test_layer0_progression.py` (#665) — `progression_pattern(movement_patterns)` crosswalk → rx key; 12 tests incl. a cross-check that every target is a real `PROGRESSION_RULES` key.
- **`init_db.py` `_PG_MIGRATIONS`** (#666) — `ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS layer0_exercise_id TEXT` + `(user_id, layer0_exercise_id)` index (end of the list, ~line 2325).
- **`rx_engine.py`** (#666) — `current_rx_by_layer0_id(db, user_id, layer0_exercise_id)` (mirrors `current_rx()`, keys off the EX-id; short-circuits on absent id) + `tests/test_rx_engine_layer0_id.py` (6 tests).
- **`init_db.py` `_PG_MIGRATIONS`** (#667) — 16 idempotent name-keyed `UPDATE current_rx SET layer0_exercise_id='EXnnn' WHERE exercise='<name>' AND layer0_exercise_id IS NULL` (end of the list).

## 4. Code/tests
All green: crosswalk 12, rx-engine-by-id 6, init_db/rx/training 58. No DDL beyond the additive `current_rx` column.

## 5. Manual verification
None gating. The visible #335 win only appears after PR 4 (below) lands and a plan is (re)generated.

## 6. Next session pointers

### 6.1 REMAINING WORK (precise, Rule #11)

**(A) Four NEW layer0 exercises — Trigger #2, NEEDS Andy per-entry sign-off first.**
Andy ruled (2026-06-16) that `Row` / `Curl` / `Sit Up` / `KB Halo` map to no existing layer0 entry and "need a new value":
- **Barbell Row** (bent-over) — bilateral horizontal pull; distinct from EX078 Single-Arm DB Row (unilateral) / EX079 Seated Cable Row (machine). Movement: `Pull-H` → rx `Pull`.
- **Biceps Curl** (plain, supinated) — distinct from EX234 Hammer Curl (neutral). Movement: accessory; no clean layer0 pattern → rx `Various` (or add a curl pattern). Elbow-flexion isolation.
- **Sit-Up** — full trunk flexion; distinct from EX224 Bicycle Crunch / EX225 V-Sit. Movement: `Anti-Extension`? No — it's trunk *flexion* (not anti-); → rx `Core`.
- **KB Halo** — loaded shoulder/thoracic mobility (warmup). Movement: `Rotation`/mobility → rx `Mobility` or `Rotation`.
**OPEN FORK for Andy (surfaced, awaiting answer):** full prescribable 0B entries (added to `sport_exercise_map` so the synthesizer can program them) vs **identity-only anchors** (exist in `layer0.exercises` so rx history maps, but NOT prescribed). Barbell Row + Biceps Curl read as legit library gaps (full entries); Sit-Up + KB Halo are marginal for an expedition-AR athlete (identity-only candidates).
**Mechanics:** new EX-ids start at **EX246** (current max active = EX245). Add via an `etl/migrations/layer0/00NN_*.sql` migration (supersede-pattern not needed — pure additions; bump the 0B etl_version per convention) applied via the **`layer0-apply`** Action (Andy one-tap). Then a follow-up `_PG_MIGRATIONS` backfill: `UPDATE current_rx SET layer0_exercise_id='EX246' WHERE exercise='Row' …` for the 4. Check the existing `etl/migrations/layer0/` ADD pattern + `validate_layer0` FK checks (the #648 exercises-FK validator will gate dangling refs).

**(B) PR 4 — the surface fix (the visible #335 win).**
- `layer4/rx_wire.py` `apply_current_rx`: look up `current_rx_by_layer0_id(db, user_id, ex.exercise_id)` FIRST (the EX-id the synthesizer emits); fall back to the name path only when it returns None (rows not yet backfilled). Update the `rx_wire: hits=…` print + tests.
- **Phase-aware %1RM load (D5b):** est-1RM from the athlete's logged best (Epley — `calculations.epley_1rm` exists), then set the working weight from the **plan phase's prescribed reps** (Base/Build/Peak/Taper, from the session's `SessionPhaseMetadata`/the dose policy in `Layer4_StrengthProgramming_Phase2_Design_v2`) via a standard %1RM/RPE table (e.g. Brzycki/Epley reverse; 5RM≈87%, 8RM≈80%, 12RM≈67%). Render `{phase sets} × {phase reps} @ {derived load}` (the template already prepends `sets × reps @`; `_render_current_rx` returns load-only). Keep `first_exposure` as the genuine no-history fallback. NOT a Trigger #1 (deterministic table, not an LLM prompt), but it is coaching-science content — keep the table cited.
- Bump `hashing.LAYER4_PROMPT_REVISION` only if the synthesis prompt body changes (it doesn't here — rx_wire is post-synth, outside the cache; a `current_rx`/backfill edit updates the rendered load on next read without invalidating blocks, per spec §9). Verify a fresh plan via `neon-query` on `plan_sessions` (expect non-`first_exposure` loads for Andy's backfilled lifts).

### 6.2 Alternative pivots
#423 (synth thinking-budget latency, high-prio), #592/#593 event-windows, #427/#428/#429 determinism epic.

### 6.3 Operating notes for next session
1. `CLAUDE.md` (Rule #13). 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md`. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned
| # | Decision | Picked by |
|---|---|---|
| 1 | Single source of truth = layer0 EX-id (no alias bridge) | Andy |
| 2 | Phase-aware %1RM load model (not increment) | Andy |
| 3 | Identity + load model one arc, split PRs | Andy |
| 4 | Backfill history to EX-ids (HITL map) | Andy |
| 5 | 16-name map confirmed; Row/Curl/Sit Up/KB Halo → 4 new exercises | Andy |
| 6 | Crosswalk in code (not a layer0 column) | Claude |

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `layer0_progression.progression_pattern` present + 12 tests | ✅ (#665 merged) |
| `current_rx.layer0_exercise_id` ALTER in `_PG_MIGRATIONS` | ✅ init_db.py ~2332 (#666) |
| `rx_engine.current_rx_by_layer0_id` present + 6 tests | ✅ (#666) |
| 16 backfill UPDATEs in `_PG_MIGRATIONS` | ✅ init_db.py (#667) |
| PRs #662–#667 merged to `main` | ✅ |
| `CURRENT_STATE.md` last-shipped = #335 Phase-2b arc | ✅ |

## 9. Files shipped
**Substantive:** `layer0_progression.py`, `rx_engine.py`, `init_db.py` (+ design doc, 3 test files) — across 4 PRs (each ≤5 files).
**Bookkeeping:** `CURRENT_STATE.md`, this handoff, #335 issue comment.

## 10. Carry-forward
None new beyond the remaining-work spec above (tracked on #335 + here).

---

**End of handoff.**
