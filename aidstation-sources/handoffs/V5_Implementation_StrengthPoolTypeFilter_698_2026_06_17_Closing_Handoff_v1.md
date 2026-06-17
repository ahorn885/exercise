# #698 Finding 2 — Type-filter the strength feasible pool — Closing Handoff

**Session:** Continued the 6/17 #692/#698 cardio-catalog thread (Andy: "check it out and keep working" on the #692 closing handoff). Shipped the recommended first build: the **#698 Finding 2** strength-pool type leak. Then answered Andy's two follow-up scoping questions (detailed breakdown + recovery/cardio session-typing) as findings, not builds.
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_IndoorBikeFold_692_2026_06_17_Closing_Handoff_v1.md`
**Branch:** `claude/admiring-cori-hjdqaq`
**Status:** committed + pushed; **PR [#704](https://github.com/ahorn885/exercise/pull/704) MERGED** (auto-merge SQUASH; deterministic, no trigger).

---

## 1. What shipped (PR #704)
**The bug (#698 Finding 2):** the strength pool was built with **no `exercise_type` filter**, so every `sport_exercise_map`-mapped `0B` exercise was a candidate regardless of type. A cardio/skill drill (e.g. `EX073 Threshold Intervals (Bike)`, an `Interval / Tempo` row mapped to cycling) was a **structurally-valid** `strength_exercises[*].exercise_id` the synthesizer could pick — i.e. mis-prescribe as a strength lift for a cycling athlete who owns a trainer.

**The fix — `layer4/per_phase.py`:**
- New module constant `_STRENGTH_POOL_EXERCISE_TYPES = frozenset({"strength","power","loaded carry","plyometric","isometric"})` (lowercased) + helper `_is_strength_pool_type(exercise_type)` that compares `.strip().lower()` (case-insensitive — **prod values are title-case** `"Strength"`; mirrors the existing `_strength_pattern_match` 0B-vocab match, tolerates casing/whitespace drift).
- `compute_feasible_pool_ids` (the SDK enum bounding `strength_exercises[*].exercise_id`): skip rows where `not _is_strength_pool_type(rx.exercise_type)`. **Rule #15:** prints `compute_feasible_pool_ids: non-strength-type dropped [<type>=<n>, …]` so a "missing exercise" in a strength session is attributable in prod.
- `_format_strength_exercise_pool` (the rendered pool the synthesizer reads): added `and _is_strength_pool_type(rx.exercise_type)` to the `cands` comprehension — keeps the rendered list and the structural enum **in lockstep**.

**The allowlist = the Andy-ratified "resistance set"** (chosen via `AskUserQuestion` 2026-06-17, "I think the resistance set is correct"): `Strength`, `Power`, `Loaded Carry`, `Plyometric`, `Isometric`. Excluded: cardio (`Interval/Tempo`, `Aerobic/Endurance`), skill (`Technical/Skill`, `Agility`, `Balance/Proprioception`), recovery/mobility (`Mobility`, `Flexibility/Stretching`, `Recovery/Soft Tissue`, `Breathwork`, `Activation/Primer`).

**Tests — `tests/test_layer4_strength_pool.py` (+4):** `_rx` fake gained an `exercise_type="Strength"` default (the duck-typed fakes had no such attr → would `AttributeError` under the new filter). New: rendered pool drops non-strength types; keeps Loaded Carry/Plyometric/Isometric; case-insensitive (`"strength"` lowercase resolves); `compute_feasible_pool_ids` excludes non-strength types. Full suite **2589 passed / 30 skipped**.

**Triggers:** none. Deterministic filter, no prompt/vocab/schema/DDL.

## 2. Andy's two follow-up scoping questions (answered as findings — NOT built)
Posted as a structured comment on **#698** (the full active 0B `exercise_type` breakdown table + these two gaps).

**(A) No recovery / mobility / stretching session type exists.** Session `kind` is enum `["cardio","strength","rest"]` in `layer4/per_phase.py:479` (also `plan_refresh.py:250` `[cardio,strength]`, `single_session.py:255` `[cardio,strength]`, `race_week_brief.py:235`). So the ~28 active rows of `Mobility` (4) / `Flexibility/Stretching` (6) / `Recovery/Soft Tissue` (1) / `Breathwork` (1) / `Activation/Primer` (16) have **no prescription home** — they could only ever have surfaced by leaking into the strength pool (now closed). Andy's intent: "scope things like recovery / stretching / mobility sessions which are separate from other training sessions." → a dedicated recovery/mobility session `kind` is **Trigger #1 (prompt)** + **Trigger #3 (schema — the `kind` enum + payload contract is a cross-layer surface)**. Needs design before build.

**(B) Cardio modality is free-composed, not catalog-driven** (confirms #692 §4b / #698 prior comment). Cardio is `cardio_blocks` the synthesizer **free-composes** from prompt zone/interval guidance; the `Interval/Tempo` + `Aerobic/Endurance` `0B` rows are **never fed to the model** — there is **no cardio analog of `_format_strength_exercise_pool`** (only the strength pool is rendered). Andy asked "im not sure if the LLM is just doing that on its own right now?" — **Yes, it is**, ungrounded. Wiring the cardio catalog in (so the agent prescribes type-aware threshold/VO2/sweet-spot from the catalog) is **Trigger #1** and **overlaps #337**. Needs design before build.

## 3. The active 0B `exercise_type` vocabulary (for the next session)
Parsed from `etl/output/layer0_etl_v1.8.0.sql`, `superseded_at IS NULL`: `Strength` 38, `Technical/Skill` 54, `Isometric` 16, `Activation/Primer` 16, `Power` 8, `Plyometric` 7, `Interval/Tempo` 6, `Flexibility/Stretching` 6, `Loaded Carry` 5, `Mobility` 4, `Agility` 4, `Balance/Proprioception` 3, `Aerobic/Endurance` 3, `Recovery/Soft Tissue` 1, `Breathwork` 1. (Note casing: real data is title-case; many test fixtures use lowercase `"strength"` — the filter is case-insensitive by design.)

## 4. Verification
- Full Python suite **2589 passed / 30 skipped** (`/tmp/venv`, full `tests/` run). No DDL/migration → no layer0-gate / `layer0-apply` needed.
- CI green on #704 (Python unit suite / JS harness / Layer 0 integrity gate); auto-merge SQUASH landed it.

## 5. Files
**Substantive:** `layer4/per_phase.py`, `tests/test_layer4_strength_pool.py`. **Bookkeeping:** `CURRENT_STATE.md`, this handoff, #698 comment.

## 6. Next pointers (Rule #13 read order): `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `verify-handoff.sh`.
**Continue the cardio-catalog / session-typing thread (awaiting Andy's direction on §2):**
1. **Recovery/mobility session type** (Trigger #1 + #3) — give the orphaned recovery/mobility/stretching catalog a prescription home; design the new `kind` + how it's scheduled (session grid already has `mobility`/`yoga` discipline-hour weights at `session_grid.py:75-76`).
2. **Cardio catalog → type-aware structured intervals** (Trigger #1, overlaps #337) — a cardio analog of the strength pool render so the agent prescribes threshold/VO2/sweet-spot from the catalog instead of free-composing.
Other open: #690/#624/#689 (Trigger #1 prompt); #283 (FIT-decode prod log). **STILL OWED (carried):** post-#572 live T3 *refresh* re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify (Andy-action).

---

**End of handoff.**
