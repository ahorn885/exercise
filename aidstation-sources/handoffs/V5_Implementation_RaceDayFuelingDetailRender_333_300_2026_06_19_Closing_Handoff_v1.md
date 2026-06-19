# #333 / #300 — race-day fueling detail render (finish Layer 5A nutrition UI) — Closing Handoff

**Issues:** [#333](https://github.com/ahorn885/exercise/issues/333) (Plan UI render gaps — "Sparse daily view" nutrition render) + [#300](https://github.com/ahorn885/exercise/issues/300) item 2 (surface the full race-day fueling detail). Both under #295 / #201.
**Branch:** `claude/cardio-prescription-next-steps-dgbb1l`. **PR pending Andy's go (PR-gated).**
**Predecessor:** `handoffs/V5_Implementation_StructuredCardioPrescription_MeasuredPhysiology_337_2026_06_19_Closing_Handoff_v1.md`.

> **The #337 handoff named #333 as the next move. Assessment first revealed #333's nutrition render + #300's "dropped 2E nutrition" are STALE — Layer 5A already consumes and renders both.** The only genuinely-undone piece was the **full race-day fueling detail** (caffeine / formats / protein-after-hr / sleep-dep / notes), which `layer5/builder.py` passes through but `view.html` truncated to CHO/Na/fluid. One purely-additive template change closed it. Suite green at 2768.

---

## 1. What happened (in order)

1. **Rule #9 session-start sweep clean** (`verify-handoff.sh` green; #337 §8 anchors on-disk; tree clean on `claude/cardio-prescription-next-steps-dgbb1l`).
2. **Assessed the #337 handoff's "Next moves" against on-disk reality before touching anything.** #337 named **#333** (Plan UI render gaps) as next move #1, "close out what's renderable now." Reading #333 + its comment: everything renderable-now already shipped via #499; the only open item ("Sparse daily view") was split into **nutrition (blocked on #300)** and **weather (blocked on #289)**.
3. **Andy picked #300 (nutrition wiring) as the actionable next step** (AskUserQuestion).
4. **Investigation surfaced a major drift:** `Layer2EPayload` is **passed into `per_phase.render_user_prompt` but never rendered** (dead-passed) — *however* **Layer 5A (`layer5/`, `PlanNutrition`) already consumes the entire 2E nutrition output**:
   - `per_phase_baseline` = passthrough of 2E `daily_nutrition_baseline`
   - `days: list[DayNutrition]` = per-day load-modulated kcal/macros/`fueling_note` (redistributes, doesn't inflate, the 2E weekly energy)
   - `race_fueling: list[RaceFuelingPlan]` = per-event wrap of 2E `race_day_fueling` (full detail)
   - **Wired:** `routes/plan_create.py` runs `generate_and_persist_plan_nutrition` post-`ready`, the view route loads `load_plan_nutrition_by_version` → `nutrition` + `nutrition_by_date`, and there's a manual `regenerate_nutrition` endpoint.
   - **Rendered:** `templates/plan_create/view.html` shows the phase-baseline card (kcal + C/P/F), per-day fuel card (`total_kcal` + macros + `fueling_note` + load-tier chip), and per-day race-day fueling on race days.
   So **#333's nutrition render and #300's "computed-then-dropped" premise are stale** — Layer 5A shipped after those issues were last updated (2026-06-11). Building "render 2E nutrition on the UI" would have duplicated existing code.
5. **Pinned the one real remaining gap.** `RaceFuelingPlan` carries `protein_after`, `caffeine`, `recommended_formats`, `blocked_formats`, `sleep_dep_overlay_applies`, `notes` (all populated by `layer5/builder.py:205-218`), but `view.html`'s `.race-fuel` block rendered **only** event name + CHO/Na/fluid per-hour bands. That is exactly **#300 item 2** ("the full race-day fueling detail: caffeine/formats/protein-after-hr").
6. **Andy ratified the narrowed slice (AskUserQuestion): finish the race-day fueling detail render, full detail.** Built it.

## 2. What shipped

Purely-additive Jinja in `templates/plan_create/view.html`'s `.race-fuel` block (inside the existing `dn.is_race_day` → `for rf in nutrition.race_fueling` loop), after the CHO/Na/fluid `rail-note`:

- **protein-after-hr** — `protein {low}–{high} g/h after hr {n}` (from `rf.protein_after` tuple), when present.
- **caffeine plan** — `caffeine: {timing}` + optional `· pre-race {mg} mg` + `· {mg}/h` + `— {notes}` (from `rf.caffeine` `CaffeineRacedayPlan`), when present.
- **recommended formats** — `formats: {a, b, …}` (joined `rf.recommended_formats`), when non-empty.
- **blocked formats** — `avoid: {a, b, …}` (joined `rf.blocked_formats`), when non-empty.
- **sleep-dep overlay** — a `chip warn` "sleep-dep fueling overlay" when `rf.sleep_dep_overlay_applies`.
- **notes** — each `rf.notes` entry as a `day-fuel-note` paragraph.

Reuses existing CSS classes (`rail-note`, `chip warn`, `day-fuel-note`) — **no new CSS, no route change, no schema change, no prompt change, no cache bump, no migration.** All fields were already passed to the template.

## 3. Ratified decisions (Andy, this session)

1. **Slice = finish the race-day fueling detail render** (Option C's remaining gap), **full detail** (caffeine + formats + protein-after + sleep-dep + notes). Deferred: #300 item 1 (the per_phase plan-gen prompt grounding — "Option A") — `PlanSession` has no nutrition output field, so that payoff is prose-only fuel cues and it's a Trigger #1 prompt change for another session.

## 4. Validation

- **Full suite 2768 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`).
- Extended `tests/test_plan_view_nutrition_render.py`: the `_race_fueling()` fixture now populates `protein_g_per_hr_after_hr_n`, `caffeine_plan`, `recommended_formats`/`blocked_formats`, `sleep_dep_overlay_applies`, `notes`; `test_renders_plan_level_and_per_day_nutrition` adds 9 assertions covering each new rendered field. This is a *real* `view.html` render (Jinja against real `PlanNutrition`), so a data-binding typo would fail the test.
- **1 substantive file** (`templates/plan_create/view.html`) + 1 test file — well under the 5-file ceiling.

## 5. Manual verification owed + next pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Owed (Andy-action, live-verify):**
1. Open a `ready` plan with a target race in scope (`/plans/v2/<id>`) → confirm the race day's fuel card now shows caffeine/formats/protein-after/notes (not just CHO/Na/fluid). Nutrition is deterministic (zero-LLM) so a regenerate via the Nutrition card's button refreshes it without a plan rebuild.

**Next moves (work these next):**
1. **#300 item 1 — render `daily_nutrition_baseline` into the per_phase plan-gen PROMPT ("Option A").** Trigger #1 (prompt design). Note the constraint found this session: `PlanSession` has **no** nutrition/fueling field (only `RacePlan`/race-week-brief does), so the synthesizer can only act on a baseline via prose (`session_notes` fuel cues on long/quality days). Proposed (un-ratified) wording is in the chat transcript of this session — a `# Fueling awareness` section parallel to #337's `# Cardio programming` + a suppress-on-empty `format_nutrition_baseline(layer2e_payload, phase)` helper. Decide whether the prose-only payoff justifies the cache bump before building.
2. **#300 item 3 / #307 — `coaching_flags` dead channel.** 2E's 6 coaching flags + the sleep-dep/heat-acclim/dietary overlays render-or-drop. One generic flag-render block un-orphans ~6 surfaces (per #295 root-cause pattern 1).
3. **#304 — Layer-1 captured-but-not-threaded sweep.** Per-field thread-or-stop decisions. Note #337 already threaded the `Layer1Performance` baselines (`hrmax_bpm`/`lactate_threshold_hr_bpm`/`cycling_ftp_w`/`running_threshold_pace_sec_per_km`/`css_swim_sec_per_100m`) that #304's original sweep missed.
4. **#333 fully closeable** once #300 (nutrition, now effectively done bar item 1's prompt) + #289 (weather, iceboxed) land — only the weather render remains for the "Sparse daily view" item.

## 6. Deferred edits (Rule #11)

None — the slice is fully built.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Race-fuel render | `templates/plan_create/view.html` | `.race-fuel` block: `rf.protein_after`, `rf.caffeine.timing`, `rf.recommended_formats \| join`, `rf.blocked_formats \| join`, `rf.sleep_dep_overlay_applies` ("sleep-dep fueling overlay"), `for n in rf.notes` |
| Test | `tests/test_plan_view_nutrition_render.py` | `_race_fueling()` populates `caffeine_plan`/`protein_g_per_hr_after_hr_n`/formats/notes; `test_renders_plan_level_and_per_day_nutrition` asserts `"caffeine: from hr 4"`, `"protein 5–10 g/h after hr 6"`, `"formats: gel, drink mix"`, `"avoid: solid bar"`, `"sleep-dep fueling overlay"`, `"start fueling early"` |
| Suite | `tests/` | `/tmp/venv/bin/python -m pytest tests/ -q` → 2768 passed / 30 skipped |
| Drift (no-op, verified) | `layer5/` + `routes/plan_create.py` | Layer 5A `PlanNutrition` already consumes 2E `daily_nutrition_baseline` + `race_day_fueling`; already wired + rendered (so #333 nutrition render / #300 "dropped" are stale) |
| Issues | #333 (nutrition render commented done bar weather), #300 (item 2 done) | — |

## 8. Carry-forward

- **#333/#300-item-2 race-day fueling detail render BUILT, suite green at 2768.** PR pending Andy's go. Live-verify owed (open a race plan, check the fuel card).
- **DRIFT recorded:** Layer 5A already un-orphaned 2E nutrition (baseline + race-day fueling) into a per-day UI render; #300 items 1 (prompt) + 3 (flags) remain; #333 needs only the #289 weather render to fully close.
- **STILL OWED (carried, unchanged):** #337 measured-physiology live-verify; #698 C1/C2 live-verify + Part-A item (b); post-#572 live T3 refresh re-verify (Rule #14); #430 Slice C / #679 EX-id self-heal live-verify; #698 Slice 3b + race-week-brief recovery live-verify; #732 parked.
