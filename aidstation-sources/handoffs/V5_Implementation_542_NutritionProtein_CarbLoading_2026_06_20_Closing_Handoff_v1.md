# V5 Implementation — #542 Plan-Nutrition Protein Fix + Race-Week Carb Loading — Closing Handoff v1

**Date:** 2026-06-20
**Branch:** `claude/jolly-clarke-vq64qa`
**Commits:** `055631e` (protein bands, #542) · `a4ed86e` (carb loading)
**PR:** opened this session (PR-gated; auto-merge enabled)
**Issue:** #542 — closed `completed`

---

## 1. What shipped

A direct-task session on **#542** ("Plan nutrition: daily protein target is too low and macro split looks off"). Two contained changes, two commits.

### (1) Protein/macro fix — #542 (`055631e`)
The Layer 2E per-phase **protein bands** sat at or below the modern trained-athlete evidence floor (Base floored at **1.4 g/kg**), so generated plans under-recommended protein on the daily nutrition targets and the plan-view fuel chips. Raised to evidence-based ranges for trained endurance / multi-sport athletes:

| Phase | protein_low → high (g/kg) |
|---|---|
| Base | 1.4–1.7 → **1.6–1.8** |
| Build | 1.6–1.9 → **1.7–2.0** |
| Peak | 1.7–2.0 → **1.8–2.2** |
| Taper | 1.6–1.9 → **1.8–2.0** |

CHO bands (5–12 g/kg by phase) and the fat floor (1.0 g/kg) were **reviewed and left unchanged** — already evidence-aligned. Anchors: Kato et al. 2016 (IAAO — endurance requirement ~1.65 g/kg, safe intake ~1.83 g/kg on training days), Morton et al. 2018 (~1.6 g/kg lean-mass breakpoint), ISSN/Jäger 2017 (1.4–2.0 g/kg), Helms et al. 2014 (Taper held high — race-week mild deficit, protein spares lean mass). Net effect: an endurance athlete now lands ~1.7–2.0 g/kg by phase (was ~1.5–1.8).

### (2) Race-week carb loading — Layer 5A, NEW (`a4ed86e`)
Built **entirely in Layer 5A**. The design question was where to gate carb loading; Andy's call — *"we primarily train endurance athletes so assume all events are ≥90 min"* — removed the >90-min eligibility gate, which removed the only reason to reach into Layer 2E for event duration. So this lives in 5A with **no cross-layer schema change** (deliberately avoided the Trigger #3 route — simpler, and the 2E→5A contract is untouched).

Mechanics: the **2 calendar days before each race event** (`_CARB_LOAD_DAYS = 2`) pin carbohydrate at **10 g/kg** (`_CARB_LOAD_G_PER_KG`) for glycogen supercompensation (ACSM/AND/DC 2016: 10–12 g/kg/day for 36–48 h before events >90 min). On a carb-load day protein holds at the phase g/kg, fat holds at the phase value (already near the 1.0 g/kg floor for endurance athletes — loading runs low-fat/low-fibre), and **total energy is driven up** (CHO is the fixed target, not the residual — loading *adds* energy, it doesn't redistribute it). The race day itself is excluded (it fuels per hour via `race_fueling`).

Surfacing + bookkeeping:
- `DayNutrition.carb_loading_applied: bool` → a "🍝 carb load" chip + a carb-load note on `templates/plan_create/view.html`.
- `WeekReconciliation.carb_loading_surplus_kcal: int` records the deliberate surplus, so the reconciliation stays honest and the invariant **Σ(per-day total_kcal) == Σ(weekly_assigned_kcal)** holds whether or not loading is active.
- `build_plan_nutrition` restructured into a clean **3-pass** flow: (1) per-week redistribution baseline → (2) per-day records with the carb-load override → (3) week reconciliation built from the final per-day totals.

Andy dogfood (80 kg, PGE race Jul 17): Jul 15–16 each show **800 g CHO** (10 g/kg) + a "Carb-load day" note; the race day stays on the per-hour fueling plan.

---

## 2. Decisions made

- **Carb loading in 5A only, no 2E change** — Andy removed the duration gate ("assume all events ≥90 min"), so every target event with a race-day fueling plan qualifies. Identified the loading window from `race_event_ids_by_date` (events that already have a fueling plan). No new 2E field, no cross-layer trigger.
- **Loading adds energy** (total driven up by the 10 g/kg CHO), tracked as `carb_loading_surplus_kcal` rather than silently breaking the weekly reconciliation. The reconciliation invariant is preserved by summing the final per-day totals.
- **Protein bands** raised but CHO/fat left alone (reviewed, already evidence-based). Taper protein held high deliberately (lean-mass preservation in the race-week deficit).
- **Closed #542 `completed`** — both acceptance criteria met (protein in an evidence-based g/kg range; CHO/fat reviewed against a reference day; macros sensible on the fuel chips), plus carb loading as a related improvement.

---

## 3. Files changed (substantive)

**Commit `055631e` (protein, #542):**
- `layer2e/builder.py` — `_PHASE_MACRO_BANDS` protein_low/high raised; rationale comment block.
- `aidstation-sources/specs/Layer2E_Spec.md` — §5.4.2 macro-band table + rationale bullet.
- `tests/test_layer2e.py` — band assertions updated to the new ranges.

**Commit `a4ed86e` (carb loading):**
- `layer5/builder.py` — `_CARB_LOAD_G_PER_KG`/`_CARB_LOAD_DAYS` constants, `_carb_load_macros`, `_carb_load_note`, carb-load window computation, 3-pass `build_plan_nutrition`, module-docstring carb-loading section; `timedelta`/`Any` imports.
- `layer5/payload.py` — `DayNutrition.carb_loading_applied` + `WeekReconciliation.carb_loading_surplus_kcal` (both additive, defaulted → backward-compatible with persisted payloads).
- `templates/plan_create/view.html` — carb-load chip in the day-fuel block.
- `tests/test_layer5_nutrition_builder.py` — +3 cases (window placement/macros, surplus/reconciliation, no-event guard) + `_race_fueling`/`_race_week` helpers.
- `aidstation-sources/specs/Layer2E_Spec.md` — resolved the dangling carb-loading open item (cross-ref to the 5A implementation).

---

## 4. Test status

Full suite **2836 passed / 30 skipped** (`/tmp/venv/bin/python -m pytest tests/`). The 2 warnings are pre-existing in `tests/test_layer3b_builder.py` (unrelated). Local run only — container can't reach Neon; required CI checks (Python unit suite / JS harness / Layer 0 gate) run on the PR.

---

## 5. Open items / owed

- **LIVE-VERIFY (Andy-action, can't run from container):** after deploy, regenerate a plan and confirm (a) the fuel chips show the higher per-phase protein, and (b) the 2 days before a race event show the "🍝 carb load" chip + ~10 g/kg CHO, while the race day keeps the per-hour fueling block.
- **Invalidation note:** 2E/5A are deterministic content-hashed builders — there is **no LLM-prompt-revision constant** to bump. The new protein bands + carb loading apply on the next Layer 2E / Layer 5A run (new plan generation, a 2E input change, or a manual 2E invalidation). Already-cached 2E payloads keep the old bands until they re-run. No migration, no public-schema DDL.

---

## 6. Operating notes for next session

### 6.3 Session-start read order (Rule #13)
1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — what just shipped + current focus
3. `CARRY_FORWARD.md` — rolling cross-session items (the "Provider integrations & API — ACTIVE THREAD" is the live next move)
4. This handoff
5. `./scripts/verify-handoff.sh` — automated anchor sweep

**Next move (carried, unchanged):** the provider integrations & API thread — #681 §4 canonical-store build wave, live-provider OAuth/webhook wiring, and #682 (AIDSTATION API). Nutrition work for #542 is complete.

---

## 7. Gut check

- **Risk:** carb-load days produce large single-day totals (~4,500 kcal for an 80 kg athlete). That is correct for deliberate glycogen loading on low-volume taper days, but it's a visible jump on the plan view — the chip + note explain it, and the reconciliation surplus documents it. If it reads as alarming in practice, the note wording is the lever, not the macro logic.
- **What might be missing:** carb loading keys off `race_event_ids_by_date` (events that have a race-day fueling plan). An event with a date but no fueling plan won't load — correct by design, but worth confirming all target events get a 2E fueling plan in practice (they do today).
- **Best argument against:** loading total isn't rounded to the 25-kcal grid (it's the exact macro sum). Minor display inconsistency vs normal days; chose precision of the CHO target over grid-tidiness. Easy to round if Andy prefers.

---

## 8. Anchor table (Rule #10 — file → anchor → check)

| File | Anchor string | Check |
|---|---|---|
| `layer2e/builder.py` | `"protein_low": 1.6` (Base row of `_PHASE_MACRO_BANDS`) | grep |
| `aidstation-sources/specs/Layer2E_Spec.md` | `bands raised 2026-06-20, issue #542` | grep |
| `aidstation-sources/specs/Layer2E_Spec.md` | `Resolved 2026-06-20 (issue #542 follow-on)` | grep (open-item) |
| `layer5/builder.py` | `_CARB_LOAD_G_PER_KG = 10.0` | grep |
| `layer5/builder.py` | `def _carb_load_macros(` | grep |
| `layer5/builder.py` | `Pass 2 — per-day records. Carb-load days pin CHO` | grep |
| `layer5/payload.py` | `carb_loading_applied: bool = False` | grep |
| `layer5/payload.py` | `carb_loading_surplus_kcal: int = 0` | grep |
| `templates/plan_create/view.html` | `🍝 carb load` | grep |
| `tests/test_layer5_nutrition_builder.py` | `def test_carb_loading_applies_two_days_before_race` | grep |

---

*End of handoff.*
