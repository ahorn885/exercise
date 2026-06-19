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

1. **Slice = finish the race-day fueling detail render**, **full detail** (caffeine + formats + protein-after + sleep-dep + notes).
2. **#300 item 1 is obsolete — do NOT build it.** Andy (this session): nutrition is generated *separately, after* the training plan, and *consumes* the training plan as input (one-way training→nutrition dependency — this is the agreed architecture, implemented as Layer 5A reading `plan_sessions` post-`ready`). Item 1's proposal (render `daily_nutrition_baseline` into the *training* plan-gen prompt) inverts that dependency and double-handles nutrition. `daily_nutrition_baseline` is already consumed — by Layer 5A, in the correct direction — so the orphan-sweep's "wire it or drop it" mandate is satisfied. **`PlanSession` carrying no nutrition field is correct-by-design, not a limitation.** Strike item 1; do not add a `# Fueling awareness` prompt section.

## 4. Validation

- **Full suite 2768 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/ -q`).
- Extended `tests/test_plan_view_nutrition_render.py`: the `_race_fueling()` fixture now populates `protein_g_per_hr_after_hr_n`, `caffeine_plan`, `recommended_formats`/`blocked_formats`, `sleep_dep_overlay_applies`, `notes`; `test_renders_plan_level_and_per_day_nutrition` adds 9 assertions covering each new rendered field. This is a *real* `view.html` render (Jinja against real `PlanNutrition`), so a data-binding typo would fail the test.
- **1 substantive file** (`templates/plan_create/view.html`) + 1 test file — well under the 5-file ceiling.

## 5. Manual verification owed + next pointers

**§6.3 read order (Rule #13):** `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → this handoff → `./scripts/verify-handoff.sh`.

**Owed (Andy-action, live-verify):**
1. Open a `ready` plan with a target race in scope (`/plans/v2/<id>`) → confirm the race day's fuel card now shows caffeine/formats/protein-after/notes (not just CHO/Na/fluid). Nutrition is deterministic (zero-LLM) so a regenerate via the Nutrition card's button refreshes it without a plan rebuild.

**Next moves (work these next):**

1. **PRIMARY — #300 item 3 / #307: the `coaching_flags` dead channel.** Render-or-drop the upstream advisory flags + 2E overlays. **This is a Trigger #1 prompt change — it needs a design pass + Andy's sign-off before any code.** Actionable starting points:
   - **The problem.** Every Layer 2 builder (2A/2B/2C/2D/2E) and both Layer 3 builders emit a `coaching_flags` list, but **no Layer 4 prompt body renders any of them.** The only `.coaching_flags` reads in `layer4/` are `PlanSession.coaching_flags` (the Layer 4 *output* session flags — an unrelated `list[str]`) and the validator's `_REST_SPACING_EXEMPT_FLAGS` check. So the upstream advisory channel is systemically dead.
   - **The proven pattern to mirror.** `TrainingSubstitutionPayload.coaching_flags` IS already rendered — `layer4/per_phase.py:727` and `layer4/race_week_brief.py:862` iterate `fl.flag_type` / `fl.message`. The fix is a generic "upstream coaching flags" render block built the same way.
   - **Flag shapes differ per layer — confirm before designing the uniform render.** `Layer2ECoachingFlag` (`layer4/context.py:749`) = `flag_type` / `message` / `severity` (`info`/`low`/`moderate`/`high`) / `event_id` / `supplement_id` / `metadata`. Layer 3 uses `Layer3Observation` (`category` / `text` / `evidence_basis` / `elevates_to_hitl`). 2A–2D each have their own — `grep -n "coaching_flags" layer2*/builder.py` lists the builders (21 files carry the symbol; the builders are 2a/2b/2c/2d/2e + layer2_modality/substitution).
   - **Design decisions for the sign-off (Trigger #1):** (a) which prompts get the block — `per_phase` / `race_week_brief` / `plan_refresh` / `single_session`; (b) format + how to normalize the differing flag shapes into one render; (c) **dedup** across layers; (d) **severity filtering** — likely render `moderate`+ only, to avoid drowning the prompt in `info` noise; (e) whether to include the 2E **overlays** (`sleep_dep_overlay` / `heat_acclim_adjustments` / `dietary_pattern_adjustments`) here or separately. This block is distinct from #213 (the HITL gate / `hitl_required`) — `coaching_flags` is non-gating advisory.
   - **Scope/ceiling:** wiring all four prompt builders + a cache bump likely exceeds the 5-file ceiling — propose a shared helper (imported by all paths, à la #337's `format_measured_physiology`) and/or slice per-path. Cache: `LAYER4_PROMPT_REVISION` (currently "13") bumps if the per_phase/refresh prompt text changes. Add a Rule #15 `print()` for which flags surfaced.
   - Closes **#300 item 3** (2E flags + overlays) and **#307** together; lets the per-layer flag-render checklist items (in the 2A–2D sub-issues) close.

2. **#304 — Layer-1 captured-but-not-threaded sweep.** Per-field thread-or-stop decisions. Note #337 already threaded the `Layer1Performance` baselines (`hrmax_bpm`/`lactate_threshold_hr_bpm`/`cycling_ftp_w`/`running_threshold_pace_sec_per_km`/`css_swim_sec_per_100m`) that #304's original sweep missed.

3. **#333 fully closeable** once #289 (weather, iceboxed) lands — the nutrition side is now done; only the weather render remains for the "Sparse daily view" item.

**Do NOT do — #300 item 1 (struck this session).** Rendering `daily_nutrition_baseline` into the *training* plan-gen prompt inverts the agreed one-way **training→nutrition** dependency (nutrition generates after the plan, consuming it — Layer 5A). The baseline is already consumed by 5A in the right direction, so the orphan is closed. `PlanSession` having no nutrition field is correct-by-design. Item 1's tracker checkbox is struck as obsolete.

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
