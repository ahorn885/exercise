# #692 — Fold duplicative indoor bikes into `Cycling trainer` — Closing Handoff

**Session:** Continued the 6/17 batch. Investigated whether the four indoor bikes are duplicative (Andy's question: "what routes to them? does that engine exist?"), then shipped the ratified fold. Also ran the #698 8-exercise check and logged the findings.
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_ExerciseCull694_Tier2SubstituteRender691_2026_06_17_Closing_Handoff_v1.md`
**Branch:** `claude/intelligent-darwin-aegp1o` (harness-pinned; on `main` @ `0d4521b`)
**Status:** committed; **1 PR — auto-merge OFF** (Trigger #2 vocab + a layer0 migration Andy applies via `layer0-apply`).

---

## 1. The investigation (answering "what routes to them?")
The feasibility cascade's INDOOR tier (`layer4/session_feasibility._DISCIPLINE_INDOOR_MACHINES`) maps the 5 cycling disciplines (D-006/007/008/030/031) to `("Cycling trainer", "Stationary bike", "Spin bike", "Assault bike")` and fires when no outdoor terrain is feasible: any one present → an indoor cycling session on that machine. So **all four route**, identically — the engine just needs *one* indoor bike.
- `Cycling trainer` — also maps to 8 cycling `0B` exercises (intervals/cadence/TT). Sport-specific vessel. **Keep.**
- `Assault bike` — distinct upper-body machine. **Keep.**
- `Spin bike` + `Stationary bike` — leg-only, map to **zero** exercises, only act as the "indoor bike present" signal. **The genuine duplicates.**

## 2. What shipped
**Andy-ratified (Trigger #2): fold `Spin bike` + `Stationary bike` into `Cycling trainer`, keep `Assault bike`.**
- `etl/migrations/layer0/0012_retire_spin_stationary_bike.sql` — pure **0C** equipment-vocab supersede of the two (the picker, `routes/locales._layer0_equipment`, renders active `equipment_items`, so they vanish from it). Modeled on `0008`. **No 0B de-drift / cache bump** — a live read confirmed **zero** active exercises name them in `equipment_required`. Atomic verify block: both retired, `Cycling trainer`+`Assault bike` kept, no exercise references a folded bike.
- `layer4/session_feasibility.py` — comment only; **tuples unchanged** (back-compat, see §3).

## 3. Back-compat decision (the one tradeoff)
Truly "folding" *saved* gear means rewriting `gym_profiles.equipment` (a JSON array in a TEXT column) `Spin/Stationary bike → Cycling trainer` — a deploy-applied public migration with real risk, for a `priority:low` item. Instead: **retire from the picker only** (new gear can't be Spin/Stationary), and **keep the cascade tuples listing them** so any *already-saved* gear still routes indoors. Zero data-migration risk. The JSON remap is an **optional follow-up** if Andy wants saved gear actually rewritten.

## 4. #698 — the 8-exercise check (logged this session)
The 8 `Cycling trainer` `0B` exercises are cardio/skill types (Interval/Tempo, Technical/Skill, Isometric). **Finding 1:** the cardio engine prescribes zone/interval *blocks*, not `0B` exercise selection → these are never prescribed for cardio (orphaned). **Finding 2 (higher severity):** the strength feasible pool (`compute_feasible_pool_ids` + `_format_strength_exercise_pool`) has **no `exercise_type` filter**, and the 8 are in `sport_exercise_map`, so a cardio drill (e.g. `EX073 Threshold Intervals (Bike)`) is a valid `strength_exercises[*].exercise_id` the synthesizer can pick — i.e. can be **mis-prescribed as a strength lift**. Recommended its own deterministic fix (filter the pool to `Strength`/`Power`). Commented on #698.

## 5. Decisions / triggers
| # | Decision | By |
|---|---|---|
| 1 | Fold Spin+Stationary → Cycling trainer, keep Assault | Andy |
| 2 | Retire-from-picker only; keep cascade back-compat (no saved-gear JSON remap) | Claude (risk vs. priority:low) |
| 3 | Strength-pool type-filter (#698 finding 2) → offer as its own bug | Claude |

## 6. Verification
- Migration validated by the **CI layer0-gate** (no local PG — container has the psql client only). Applied to prod via **`layer0-apply`** after merge (Andy one-tap).
- Python suite **green** (2585 passed / 30 skipped) — no logic change (cascade comment only).

## 7. Manual verification — OWED (Andy-action)
- After merge + `layer0-apply`: the gear picker no longer offers `Spin bike` / `Stationary bike`; `Cycling trainer` + `Assault bike` remain; a cycling athlete with an indoor bike still routes indoors.
- (Carried) post-#572 live T3 refresh; #430 Slice C / #679 EX-id self-heal live-verify.

## 8. Files
**Substantive:** `etl/migrations/layer0/0012_retire_spin_stationary_bike.sql`, `layer4/session_feasibility.py` (comment). **Bookkeeping:** `CURRENT_STATE.md`, this handoff, GitHub issues #692 / #698.

## 9. Next pointers (Rule #13 read order): `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `verify-handoff.sh`.
Best next: the **#698 strength-pool type-filter** bug (deterministic, no trigger — a real correctness fix), or #690/#624/#689 (Trigger #1 prompt — trace + bring the prompt change).

---

**End of handoff.**
