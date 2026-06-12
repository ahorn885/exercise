# V5 Implementation — Track 2 slice 2b.2b: athlete-facing session-grid ceiling fields (shipped)

**Date:** 2026-06-12
**Branch:** `claude/slice-2b2b-session-grid-unit-fields`
**PR:** [#564](https://github.com/ahorn885/exercise/pull/564) — squash-merged to `main` `64bf221`
**Epic/track:** Track 2 (Determinism-First Synthesis) [#429](https://github.com/ahorn885/exercise/issues/429) — the last owed Track 2 follow-up. **Track 2 follow-up tail now fully drained.**

> **Companion PR this session:** [#563](https://github.com/ahorn885/exercise/pull/563) (docs-only) reconciled `CARRY_FORWARD.md` §1 — slice 2c.2 was reframed into the #540 terrain+craft cascade and shipped; the layer0 vocab adds (TRN-017/TRN-007) are superseded-as-blocker; snow-sports routing resolved in-code. Both #563 and #564 merged 2026-06-12.

---

## 1. What this session was

Started from a question — "are any Track 2 slices still left?" The honest answer: Track 2's core (2a/2b/2c/2d) was CLOSED, but `CARRY_FORWARD.md` had drifted (it still listed slice 2c.2 cardio routing + its prereqs as open, though they'd been reframed into #540 and shipped). Reconciled that (#563), then confirmed **slice 2b.2b** was the one genuinely-owed Track 2 item — and wired it (#564).

## 2. What shipped (PR #564)

The deterministic session-count ceiling (slice 2b.2a / `Layer4_DeterminismFirst_Synthesis_Design_v2` §5.1.1) was already live, but `per_phase` read its two athlete inputs from a **top-level payload placeholder that nothing populated**, so the grid always used spec defaults (`occasionally` / derive-10). This wires both controls end to end.

**The two fields:**
- **`two_a_day_preference`** (`never` / `occasionally` / `regularly`) — the primary categorical density control; drives the Peak sessions-per-day multiplier (`session_grid._TWO_A_DAY_DENSITY` = 1.0 / 1.5 / 1.85).
- **`peak_sessions_max`** (optional INT) — the advanced override. Authoritative when set; when NULL the grid derives the ceiling from the preference. Rejected (with a flash) outside `1..2×available_days`.

- **`init_db.py`** — `athlete_profile.two_a_day_preference TEXT` + `peak_sessions_max INTEGER` (idempotent `_PG_MIGRATIONS` ALTERs; nullable, no DB CHECK — app-layer validated, matching `doubles_feasible`/`sex`). **APPLIED on Neon by Andy 2026-06-12** (ran the two `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in the SQL editor).
- **Read-path:** the two scalars join `Layer1Availability` (§G) in `layer4/context.py`, next to `doubles_feasible`. `layer1/builder.py` reads both columns into `availability_scalars` (+ `_empty_availability_scalars`, + `_PROFILE_COLS`). `layer4/per_phase.py` now reads them from the **nested `availability`** dict (`layer1_payload["availability"][...]`) and passes to the grid.
- **Capture (both surfaces, shared parser):** `routes/onboarding._parse_schedule_form` parses both into `profile_updates` (two-a-day defaults to `occasionally` on miss; Peak cap blank → NULL, out-of-range → flash + NULL), persisted via `upsert_athlete_profile`. The onboarding `schedule` GET + the profile `edit` GET pass the prefill + choices. `templates/onboarding/_schedule_form.html` (the shared partial, included by both `onboarding/schedule.html` and `profile/edit.html`) renders the two-a-day radio + the advanced Peak-cap number.
- **`athlete.py`** — both columns added to `PROFILE_FIELDS` (allowlist gating `upsert_athlete_profile` + `get_athlete_profile`); new `TWO_A_DAY_CHOICES`.
- **`static/style.css`** — one `u-mw-120` max-width utility (the redesign forbids inline `style=`; CSP-clean).

**NO `session_grid` change** — `_peak_ceiling` already does "use `peak_sessions_max` if set, else derive from `two_a_day_preference`," so storing both raw and letting the grid derive is the minimal wiring.

## 3. Design reconciliation (read before touching these fields)

`two_a_day_preference` is **intentionally distinct** from the pre-existing `doubles_feasible`, per Design_v2 §5.1.1:
- **`doubles_feasible`** (`regularly`/`occasionally`/`no`) — whether second sessions are *realistic*; gates the second-window **scheduling** UI.
- **`two_a_day_preference`** (`never`/`occasionally`/`regularly`) — how often the athlete *wants* to train twice a day; drives the Peak session-count **ceiling**.

They sit adjacent in the same schedule form. The form copy calls out the difference ("about your target density, separate from whether doubles are feasible above"). **UX watch-item (non-blocking, flagged to Andy in PR #564):** revisit if athletes find the two questions redundant. I considered deriving `two_a_day_preference` from `doubles_feasible` (a clean no→never map), but the design deliberately separates want-vs-feasibility with distinct copy — so both are kept.

## 4. Verification

Full suite **2333 passed / 30 skipped** (2327 baseline + 6 new parser tests). CI green (Python unit suite, Layer 0 integrity gate, JS harness, Vercel preview; Real-LLM smoke skipped). **One-time cache note:** adding fields to `Layer1Availability` shifts its `model_dump()` → shifts `layer1_hash` (the key for every Layer 4 cache entry) → a harmless one-time plan-cache recompute on first post-deploy run (auto; only Andy in prod).

## 5. Owed / next move

1. **Nothing owed for this slice.** The Neon migration is applied; live the moment the deploy lands.
2. **#539** (tab-closed plan-gen crawl) — the remaining go-live blocker, now the top live move (the #540 create-path feasibility cascade is done). **← NEXT (recommended).**
3. **#540 gated tail (not Track 2 work, not a live surface):** **#557** refresh-path feasibility wiring (mirror the create wiring at `orchestrate_plan_refresh`; behind #208) + the **Track-3-gated** layer0 column lift of the discipline→terrain map. Consider closing #540 with these as residual.
4. **Quality batch:** #541 (shallow strength — prompt change, Trigger #1), #542 (low-protein macros), #543 (structured health conditions — vocab add).
5. **Pre-existing owed deploys (NOT from this slice):** confirm `layer0.skill_capability_toggles` applied on Neon (#336 gate is data-driven off it); `plan_versions.archived_at` (#531); the sleep columns (#283/#504). See `CARRY_FORWARD.md`.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` (the Track 2 §1 entry) · 4. **this handoff** · 5. `./scripts/verify-handoff.sh`. **2b.2b is shipped — Track 2's follow-up tail is fully drained.** Next live move is **#539** (§5.2). The #540 refresh tail (#557) + column lift are gated; the two-a-day-vs-doubles distinction is settled (§3) — don't re-open it.

## 6. Stop-and-asks this session
- **Trigger #3 (cross-layer surface change):** adding `athlete_profile` columns + threading the two scalars into the Layer 1 payload contract (`Layer1Availability` → `per_phase`) is a Layer 1 contract change. Put the field schema + the over-the-5-file-ceiling split to Andy via `AskUserQuestion` before building; he chose **one PR, whole vertical** on a **fresh branch** (keeping the docs PR #563 separate). No Trigger #1 (no LLM prompt body changed — the synthesis directive already consumed the grid output). No Trigger #2 (no vocab/exercise adds).

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Migration columns | `init_db.py` | `ADD COLUMN IF NOT EXISTS two_a_day_preference TEXT`, `... peak_sessions_max INTEGER` (tail of `_PG_MIGRATIONS`) |
| Payload schema | `layer4/context.py` | `class Layer1Availability` fields `two_a_day_preference` (Literal never/occasionally/regularly) + `peak_sessions_max: int \| None = Field(default=None, ge=1)` |
| Builder read | `layer1/builder.py` | `_PROFILE_COLS` contains `"two_a_day_preference"`/`"peak_sessions_max"`; `availability_scalars` + `_empty_availability_scalars` carry both |
| Consumer read | `layer4/per_phase.py` | `_availability = (layer1_payload or {}).get("availability") or {}` → `.get("two_a_day_preference")` / `.get("peak_sessions_max")` |
| Capture parse | `routes/onboarding.py` | in `_parse_schedule_form`: `two_a_day = form.get('two_a_day_preference', ...)`, `peak_sessions_max = _parse_int(raw_peak, min_=1, max_=max(1, 2 * available_days))`; `profile_updates` carries both |
| Allowlist + choices | `athlete.py` | `PROFILE_FIELDS` contains both; `TWO_A_DAY_CHOICES = ('never', 'occasionally', 'regularly')` |
| Form controls | `templates/onboarding/_schedule_form.html` | `name="two_a_day_preference"` radios + `id="peak_sessions_max"` number (`class="... u-mw-120"`) |
| Width util | `static/style.css` | `.u-mw-120 { max-width: 120px; }` |
| Tests | `tests/test_onboarding_schedule_ceiling.py`, `tests/test_layer1_builder.py` | `test_peak_cap_over_two_times_available_days_rejected`; `assert payload.availability.two_a_day_preference == "regularly"` |
| Merged | PR [#564](https://github.com/ahorn885/exercise/pull/564) | squash-merged `64bf221`; full suite 2333 |
