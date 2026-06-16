# #430 Slice C — rx write-path FK cutover to layer0 EX-ids — COMPLETE — Closing Handoff

**Session:** Continued the #335 single-source-of-truth arc into **#430's Phase-4 FK cutover** for the strength-rx write path. Shipped as **3 sequenced PRs** (dance pattern, history preserved): C1 keyed the progression off the layer0 EX-id + self-healed it on writes; C2 made the public `exercise_inventory.id` FK vestigial; C3 dropped it. Also surfaced and filed the **Garmin name-resolution gap (#679, Slice D)** discovered while answering Andy's "will garmin uploads map correctly?".
**Date:** 2026-06-16
**Predecessor handoff:** `V5_Implementation_RxWire_SingleSourceOfTruth_335_Phase2b_Complete_2026_06_16_Closing_Handoff_v1.md`
**Branches:** `claude/rxwire-single-source-truth-oasev5` (C1), `claude/rxwire-slice-c2-readers` (C2), `claude/rxwire-slice-c3-drop-fk` (C3), `claude/rxwire-slice-c-bookkeeping` (this).
**Status:** PRs **#676 + #677 + #678 MERGED** to `main`. The DROP-COLUMN migration auto-applies on the next Vercel deploy (`_PG_MIGRATIONS`, idempotent). #430 partially advanced (rx write-path FK retired; read-only routes + equipment unification remain). **#679 filed** for the Garmin resolver.

---

## 1. Session-start verification (Rule #9)
`verify-handoff.sh` clean at start; predecessor §8 anchors all present; #335 confirmed CLOSED + verified live (pv=73). Direct continuation, no drift.

## 2. Session narrative
- Andy "let's keep working" → #335 was done; chose next track via `AskUserQuestion`: **Slice C of #430**, then **Full FK cutover too**, then (on my flag that the catalog plan's *wipe* pattern would destroy the #335 baselines) **dance pattern, preserve history**, delivered as **sequenced PRs this session**.
- Mapped the read/write surface: `training_log.exercise_id` is **write-only** (never read); `current_rx.exercise_id` had **one reader** (`coaching.py`). `discipline` is read by `routes/rx.py` and has **no clean layer0 source** → kept the `exercise_inventory` read by name (flagged; full retirement is the broader #430).
- Mid-arc Andy asked **"will garmin uploads map correctly?"** → traced `garmin_fit_parser.py`: FIT emits 1,261 names, subtype-preferred; only 14 of the 20 curated map keys overlap (coarse categories). Answer: **partially, not the common case** → filed **#679 (Slice D)**.

## 3. File-by-file (shipped)
- **C1 (#676):** `layer0_progression.py` (+ `NAME_TO_EX_ID` single-source map), `rx_engine.py` (EX-id-keyed progression via `_layer0_progression_pattern` + crosswalk; self-heal `layer0_exercise_id`; drop `weight_increment` ei read; Rule #15 log), `init_db.py` (backfill generated from `NAME_TO_EX_ID`), `tests/test_rx_engine_apply_outcome_layer0.py` (new).
- **C2 (#677):** `coaching.py` (join `exercise_inventory` by name), `rx_engine.py` (stop read/return/write of public `exercise_id`; ei read by name for discipline/type/suggested_volume), `routes/training.py` + `routes/garmin.py` + `routes/natural_log.py` (drop `exercise_id` from `training_log` writes), `tests/...` (+`TestPublicFkRetired`).
- **C3 (#678):** `init_db.py` (drop `exercise_id` from `current_rx`/`training_log` CREATE TABLE; `DROP COLUMN IF EXISTS` migrations; remove backfills).

## 4. Code/tests
Full suite **2543 passed / 30 skipped** at each PR (the venv: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`). No DB exercised by unit tests; the DDL validates on deploy.

## 5. Manual verification — OWED (Andy-action)
Can't trigger from the container. Owed: log a strength session (manual or Garmin FIT) → confirm `current_rx.layer0_exercise_id` is populated on the write (the `rx_engine.apply_session_outcome: … ex_id=… layer0=y/n` log line, via `/admin/logs` + the Vercel MCP `web_fetch_vercel_url`), then a subsequent plan-gen reads it (rx_wire `id=` hit). Expect: backfilled lifts hit by EX-id; un-mapped Garmin subtypes still `first_exposure` (that's #679).

## 6. Next session pointers

### 6.1 REMAINING / FOLLOW-UPS
- **#679 — Slice D (recommended next):** FIT-name → layer0 EX-id resolver (fuzzy + HITL over Garmin's `_EXERCISE_CATEGORY_MAP`/`_EXERCISE_SUBTYPE_MAP` → layer0's ~250 qualified names). Highest dogfood impact — makes Andy's Garmin strength data render as capacity-derived loads.
- **Rest of #430:** read-only routes (`references`/`injuries`/`rx`/`purchases`) + `coaching` still read `exercise_inventory` **by name** for display fields (`discipline` has no layer0 source yet — source from the sport map); `injury_exercise_modifications` + `exercise_equipment` keep their `exercise_inventory(id)` FKs; equipment-catalog unification (`equipment_items`) untouched.

### 6.2 Alternative pivots
#423 (synth thinking-budget latency, high-prio), #592/#593 event-windows, #427/#428/#429 determinism epic.

### 6.3 Operating notes for next session
1. `CLAUDE.md`. 2. `CURRENT_STATE.md`. 3. `CARRY_FORWARD.md`. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned (this session)
| # | Decision | Picked by |
|---|---|---|
| 1 | Next track: Slice C of #430 | Andy |
| 2 | Full FK cutover (not just the movement_pattern slice) | Andy |
| 3 | **Dance** pattern (preserve #335 history), NOT wipe | Andy (after Claude flagged wipe destroys baselines) |
| 4 | Sequenced PRs C1→C2→C3 this session | Andy |
| 5 | Keep `exercise_inventory` read by NAME for discipline/type/suggested_volume (discipline has no layer0 source; rx.py needs it) | Claude (flagged) |
| 6 | No `training_log.layer0_exercise_id` (write-only column, no reader → speculative) | Claude |

## 8. Session-end verification (Rule #10)
| Check | Result |
|---|---|
| `NAME_TO_EX_ID` map in `layer0_progression.py` (single source) | ✅ layer0_progression.py |
| `_layer0_progression_pattern` + EX-id resolution in `apply_session_outcome` | ✅ rx_engine.py |
| `apply_session_outcome` result has `layer0_exercise_id`, NOT `exercise_id` | ✅ rx_engine.py |
| `coaching.py` joins `exercise_inventory` by name (`ei.exercise = cr.exercise`) | ✅ coaching.py |
| no `exercise_id` in `current_rx`/`training_log` CREATE TABLE | ✅ init_db.py |
| `DROP COLUMN IF EXISTS exercise_id` migrations for both tables | ✅ init_db.py `_PG_MIGRATIONS` |
| init_db backfill generated from `NAME_TO_EX_ID` (no literal list) | ✅ init_db.py |
| PRs #676 + #677 + #678 merged to `main` | ✅ |
| #679 (Slice D) filed; #430 commented with what shipped | ✅ |
| `CURRENT_STATE.md` last-shipped = #430 Slice C COMPLETE | ✅ |

## 9. Files shipped
**Substantive:** `layer0_progression.py`, `rx_engine.py`, `init_db.py`, `coaching.py`, `routes/training.py`, `routes/garmin.py`, `routes/natural_log.py` (+ test) — across 3 PRs (each ≤5 substantive files).
**Bookkeeping:** `CURRENT_STATE.md`, this handoff, #430 comment, #679 filed.

## 10. Carry-forward
- **Live-verify** the EX-id self-heal on a real log + downstream plan-gen (§5) — Andy-action.
- **#679 (Slice D)** — Garmin FIT-name → EX-id resolver (the real fix for "do garmin uploads map correctly").
- Standing pre-existing carry: the post-#572 live **T3 *refresh*** re-verify (Rule #14).

---

**End of handoff.**
