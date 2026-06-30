# V5 Implementation — Sign-up / Onboarding Consolidation, Phase 1: #1067 — Pack-load Weighting + Summary/Edit/Delete UX — Closing Handoff (2026-06-30)

**Branch:** `claude/dreamy-curie-r1di5z` (fresh off `main` @ `d899e02`, NOT stacked) · **Commit:** `4df9ab5` (code) + the bookkeeping commit riding the same branch · **PR:** none yet — **pushed + bookkept, holding for Andy's go** (project rule: never auto-open) · **Issue:** [#1067](https://github.com/ahorn885/exercise/issues/1067) · **Epic:** [#246](https://github.com/ahorn885/exercise/issues/246) · **Plan:** sign-up/onboarding consolidation, Phase 1 (`CARRY_FORWARD.md` arc entry, D1) · **Suite:** full `tests/` **4022 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).

**Context:** Continuation of the sign-up/onboarding consolidation arc. #257 (V3 profile fields) shipped + merged last session (PR #1074, merge `d899e02`). This session took the next Phase-1 slice, **#1067** — pack-load weighting (per D1) + the entry-form UX.

---

## 1. Session-start verification (Rule #9)

- `./scripts/verify-handoff.sh` → **clean** (no ❌); #257 anchors all present in `main` (the 4 profile columns, dietary tokens, the 2E sweat/salt split, the layer1 thread-through tests).
- HEAD = origin/main = `d899e02` (local `main` ref was stale at `f209f58`; the branch is correctly based on the latest origin/main — confirmed `git merge-base --is-ancestor HEAD origin/main`).
- **Re-grounded #1067 against current code before editing** (the D2 lesson). Findings:
  - The pack-load capture pipeline already exists end-to-end: `pack_load_repo.py` (list/add/delete) → `pack_load_history` table (`init_db.py:1909`) → `layer1/builder._load_pack_load_history` → `Layer1TrainingHistory.pack_load_history` (`PackLoadRecord`) → rendered into the **Layer 3B Block-2 goal-context excerpt** (`layer3b/builder.py:615`).
  - **Data reality (load-bearing):** there is **no separate "raced with the pack" field.** The only pack signal is `pack_load_history`, where `longest_session_hrs` is the time-under-load / deep-prior-experience proxy (e.g. a 30 h carry) and `session_count_4wk` is recent training frequency. D1's "prior race experience over recent training" therefore maps onto **these two existing fields** — `longest_carry` (experience) vs `recent_sessions` (frequency). The old render line surfaced `heaviest_kg`/`longest_session_hrs`/`records` but **not** `session_count_4wk`, and gave the reasoner **no priority guidance**.

## 2. Decisions (Andy, chat 2026-06-30)

- **D1 (pre-ratified, CARRY_FORWARD):** #1067 pack-load weighting → **PRIOR RACE EXPERIENCE over recent pack training**, landing in `layer3b/builder.py` near the `pack_load_history` read.
- **This session (AskUserQuestion):** *how* to express the D1 weighting in Layer 3B — modifying an LLM prompt body is **Stop-and-ask trigger #1**, so the wording was put to Andy. Options offered: (A) explicit guidance clause in the prompt; (B) order/label only; (C) **deterministic readiness tag computed in code**. **Andy chose C** — compute the readiness signal deterministically and render the tier, rather than instructing the LLM.

## 3. What shipped — #1067 (2 parts)

### Part 1 — deterministic load-carriage readiness (Layer 3B, Option C)

New pure helper `layer3b/builder._pack_load_readiness(plh, race_pack_weight_kg)` → `(tier, heaviest_kg, longest_carry_hrs, recent_sessions_4wk, weight_covered)`. **Experience-led tiering (D1):**

- `heaviest = max(pack_weight_kg)`, `longest = max(longest_session_hrs or 0)`, `sessions = sum(session_count_4wk or 0)`.
- `covered = race_pack_weight_kg is None or heaviest >= 0.9 * race_pack_weight_kg` (within 10% of the race demand; unknown demand → covered).
- **`established`** — `longest >= 6.0` **and** `covered` (a deep prior carry at race-relevant load; recent frequency not required — experience > frequency).
- **`developing`** — `longest >= 2.0` **or** `sessions >= 6` (some carrying base; experience still shallow, or recent frequency lifts it).
- **`limited`** — records exist but minimal carry experience and light recent training.

**Thresholds are coarse + tunable** (documented in the docstring): `≥6 h` = a real multi-hour time-under-load; `≥2 h` = a developing base; `≥6` sessions/4 wk (~1.5×/week) = enough recent frequency to reach developing without a long carry yet. **Flagged for Andy** — these embody a coaching judgment and are easy to retune in one place.

The render block at `:615` now calls the helper, emits a **Rule #15 `print`** (`[layer3b pack-load-readiness] user_id=… heaviest_kg=… longest_carry_hrs=… recent_sessions_4wk=… race_pack_weight_kg=… weight_covered=… records=… -> tier=…`), and appends `- pack_load_readiness: {tier} (heaviest_kg=…, longest_carry_hrs=…, recent_sessions_4wk=…, records=…)` to the Block-2 excerpt (was `- pack_load_training: heaviest_kg=…, longest_session_hrs=…, records=…`). Suppress-on-empty unchanged (most athletes carry no pack).

### Part 2 — summary/edit/delete UX (`templates/profile/edit.html` §C)

Once any pack-load record exists, the entry form is collapsed behind a `<details class="pf-pack-add"><summary>Add another pack weight</summary>` disclosure (mirrors the `<details>` convention already used in `templates/profile/event_windows.html` — CSP-clean, no JS). The records list (the summary) + per-row **Remove** (delete, already existed) stay visible; the athlete opens the disclosure to add another. **First-time entry (no records) shows the form directly** — no disclosure to open first. The form markup is rendered once (the `<details>` open/close straddle the `{% if pack_loads %}`), so no duplication and no new macro.

| File | Change |
|---|---|
| `layer3b/builder.py` | `+PackLoadRecord` import; new `_pack_load_readiness` helper; render block at `:615` rewired to the tier + Rule #15 log. |
| `templates/profile/edit.html` | §C pack-load: collapse the add-form behind `<details>` once records exist; bare form when empty. |
| `tests/test_layer3b_builder.py` | `+PackLoadRecord`/`_pack_load_readiness` imports; new `TestPackLoadReadiness` (6 cases: long-carry→established, frequency-only→developing, underweight cap, minimal→limited, unknown-race-weight→covered, multi-record aggregation). |
| `tests/test_redesign_profile_render.py` | `_Conn` gains a `pack_loads` fixture branch; new `test_profile_pack_load_form_collapses_once_filled` + an empty-state `pf-pack-add not in html` assertion on the existing gear-tab test. |

**Scope:** 2 substantive code files + 2 test files — under the 5-file ceiling.

## 4. Verification

- Full `tests/` **4022 passed / 30 skipped** (baseline 4015 + 7 new tests; only the 3 pre-existing #217 warnings). Single-file collection hits the documented circular-import quirk → ran with a `tests/test_layer4_*.py` front-loaded / full suite.
- `ruff` on the 2 changed prod files: `layer3b/builder.py` **2 errors before == 2 after** (`GoalViability`/`PeriodizationShape` pre-existing unused imports, left untouched per surgical-changes); my `PackLoadRecord` import is correctly seen as used. `routes/profile.py` **not touched** this session (its 6 pre-existing errors are unrelated). My edits introduced **0** new errors.
- **No `layer0-apply` owed** — no schema change. The Layer 3B Block-2 prompt text changed (`pack_load_training` → `pack_load_readiness`), which changes the **Layer 3B prompt → its cache key**; for any athlete with `pack_load_history`, 3B cold-recomputes once on next deploy/regen (expected under the partial-update model; suppress-on-empty means no-pack athletes are byte-identical). Andy is the only test athlete.

## 5. NEXT — DECIDED: Phase 1 continues with **#223 (pregnancy field, capture only)**

- **#223 — pregnancy field (capture only).** Screening Q8/`PREGNANCY` as source of truth + an explicit capture field. **DEFER the `layer2e` HITL-gate half** (gates 1-4 are dead-stubbed `_emit_hitl_items` → `[]`; the gate change is stop-and-ask trigger #4). #223 is labelled `priority:low`/`icebox` — **re-confirm with Andy it's still wanted in Phase 1** before taking.
- **#304 remains OPEN** — Part B's `_history`-lists call (medications/conditions/injury history; only the *active* lists are read) was not in D2 scope and still needs a thread-or-stop-capturing decision.
- **Then Phase 2** — #394 screening polish (D-79..D-85). **Phase 3** — #272 SMS/WhatsApp + #267 passkeys via Twilio. **Closeout** — close epic #246 once its open children land.

## 6. Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — the sign-up/onboarding arc entry (D1-D5 + Phase-1 progress)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

### §6.1 anchor table (Rule #10 — next session's Rule #9 input)

| Claim | File | Anchor / check |
|---|---|---|
| readiness helper exists | `layer3b/builder.py` | `grep -c "_pack_load_readiness" layer3b/builder.py` → 2 (def + the `:615` call) |
| experience-led tiering | `layer3b/builder.py` | `grep "longest >= 6.0 and covered" layer3b/builder.py` (present) |
| render uses the tier | `layer3b/builder.py` | `grep "pack_load_readiness:" layer3b/builder.py` (present); old `pack_load_training` gone |
| Rule #15 log | `layer3b/builder.py` | `grep "layer3b pack-load-readiness" layer3b/builder.py` (present) |
| UX disclosure | `templates/profile/edit.html` | `grep "pf-pack-add" templates/profile/edit.html` (present); `grep "Add another pack weight"` |
| regression tests | `tests/` | `TestPackLoadReadiness`, `test_profile_pack_load_form_collapses_once_filled` |
| suite green | `tests/` | `python -m pytest tests/ -q` → 4022 passed / 30 skipped |

### §6.2 #1067 status (close on merge)

Both parts shipped: Part 1 (deterministic Layer 3B readiness tier, Option C) + Part 2 (entry-form disclosure UX). → **#1067 is closeable as `completed`** when this lands. The threshold constants (`6.0`/`2.0`/`6`/`0.9`) are the one hand-tuned surface — surfaced for Andy to retune.

## 7. NEXT SESSION — continue with #223 (pregnancy capture)

**This slice is complete.** The next step in the Phase-1 sequence is **#223 — pregnancy field (capture only)**, **its own PR off `main`** — but **re-confirm with Andy first** (it's `icebox`/`priority:low`, and the `layer2e` HITL-gate half is deferred = stop-and-ask trigger #4). Then Phase 2 (#394), Phase 3 (#272/#267), then close epic #246. **STAY ON THE SIGN-UP/ONBOARDING THREAD.**

**PR state:** pushed + bookkept; opens + auto-merges (merge commit) on Andy's go (project rule: never auto-open). Branch `claude/dreamy-curie-r1di5z`.
