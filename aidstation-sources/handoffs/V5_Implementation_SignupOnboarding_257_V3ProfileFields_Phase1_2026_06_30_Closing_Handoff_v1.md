# V5 Implementation — Sign-up / Onboarding Consolidation, Phase 1: #257 — V3 Onboarding Profile Fields + Sweat/Salt Split — Closing Handoff (2026-06-30)

**Branch:** `claude/disclosures-payload-removal-p1-2v355b` *(harness-pinned name; this session's scope is #257, not disclosures — kept as-is because the harness task forbids pushing to a renamed branch without permission)* · **Commit:** `8bc0385` (code) + the bookkeeping commit riding the same branch · **PR:** none yet — **pushed + bookkept, holding for Andy's go** (project rule: never auto-open) · **Issue:** [#257](https://github.com/ahorn885/exercise/issues/257) (V3 onboarding profile fields) · **Epic:** [#246](https://github.com/ahorn885/exercise/issues/246) · **Plan:** sign-up/onboarding consolidation, Phase 1 (`CARRY_FORWARD.md` arc entry) · **Suite:** full `tests/` **4015 passed / 30 skipped** (the 3 Layer3B `evidence_basis` warnings pre-exist, #217).

**Context:** Continuation of the sign-up/onboarding consolidation arc. #304 Part B (disclosures payload removal) shipped + merged last session (PR #1073, merge `894114f`). This session took the explicit next Phase-1 slice, **#257** — the 7 tracked V3 candidates from the Section-I audit.

---

## 1. Session-start verification (Rule #9)

- `./scripts/verify-handoff.sh` → **clean** (no ❌); #304 Part B anchors all present in `main` (disclosures gone from `layer1/builder.py` + `layer4/context.py`, `disclosure_acknowledgments` table retained, `test_disclosures_dropped_from_payload` present).
- **Re-grounded #257 against current code before editing** (the D2 lesson — issue text is materially stale). Findings:
  - **V3-I-7 (supplement restructure) — ALREADY BUILT.** `athlete_supplements` table + `athlete_supplements_repo.py` (structured multi-select + free-text) + the picker in `routes/profile.py`/`templates/profile/edit.html`, consumed by `layer2e/builder.py` + `layer4/context.py`. → out of scope.
  - **V3-I-2 (macro pref) — mostly covered.** `DIETARY_PATTERN_CHOICES` already had `keto`/`paleo`/`vegan`/`low_fodmap`/… Only a distinct fat-adapted/low-carb axis was missing.
  - **V3-I-1 / V3-I-9 / V3-I-10 — genuinely new** (no sleep-consistency, hydration-baseline, or weight-trend capture existed).
  - **V3-I-4 — cross-layer.** The single `salt_electrolyte_tolerance` (low/mod/high) enum drove **both** the sodium and fluid modifiers in Layer 2E (`_salt_tolerance_modifier` → 0.8/1.0/1.2 applied to `na_*` *and* `fluid_*`). §5.8 heat overlay is a STUB.

## 2. Decisions (Andy, chat 2026-06-30)

- **D1 — scope:** build all the genuinely-new fields now. Drop V3-I-7 (already done).
- **V3-I-2:** add the fat-adapted/low-carb axis — confirmed **distinct** from keto (stricter ketosis) and paleo (food-quality framework, not a carb level). Implemented as two `dietary_pattern` tokens: `low_carb` + `fat_adapted`.
- **V3-I-3 — dropped** (CYP1A2 caffeine-sensitivity flag; not self-knowable without a genetic test, `caffeine_tolerance` already captures the usable signal).
- **D2 — V3-I-4 full scope:** split the fields **AND** rewire Layer 2E (not capture-only). This is a Stop-and-ask trigger #3 (cross-layer); Andy ratified the full rewire.

## 3. What shipped — #257 (5 fields)

| Field (V3-I-#) | Where it lives | Consumer |
|---|---|---|
| `sleep_consistency` (1) — `consistent`/`mostly_consistent`/`variable`/`highly_variable` | `Layer1Lifestyle` | capture-only (no consumer yet) |
| `low_carb` + `fat_adapted` (2) — `DIETARY_PATTERN_CHOICES` tokens | `Layer1Lifestyle.dietary_pattern` | existing dietary-pattern path |
| `sweat_rate_level` (4) — `low`/`moderate`/`high` | `Layer1Lifestyle` | **Layer 2E fluid band** (the split) |
| `daily_hydration_baseline` (9) — `low`/`moderate`/`high` | `Layer1Lifestyle` | capture-only |
| `body_weight_trend` (10) — `stable`/`gaining`/`losing`/`significant_gain`/`significant_loss` (significant = >5%/3mo) | `Layer1Performance` | capture-only |

**The V3-I-4 split (Layer 2E `_build_race_day_fueling`):** added `_sweat_rate_modifier(deployed_value)` (low 0.8 / moderate-or-unset 1.0 / high 1.2). The **fluid** band now scales on `sweat_mod`; the **sodium** band still scales on `salt_mod` (`_salt_tolerance_modifier(salt_electrolyte_tolerance)`) — independently. New `RaceDayFueling.sweat_rate_modifier_applied: float = 1.0` (default keeps the 8 direct test constructions + pre-split rows a no-op). The athlete-facing label changed "Salt / electrolyte tolerance" → "Salt / electrolyte **loss**" to read right beside the new "Sweat rate".

| File | Change |
|---|---|
| `athlete.py` | `PROFILE_FIELDS` += the 4 new columns; 4 closed-enum choice tuples (`SWEAT_RATE_LEVEL_CHOICES`, `DAILY_HYDRATION_BASELINE_CHOICES`, `SLEEP_CONSISTENCY_CHOICES`, `BODY_WEIGHT_TREND_CHOICES`); `low_carb`+`fat_adapted` added to `DIETARY_PATTERN_CHOICES`. |
| `init_db.py` | 4 idempotent `ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS … TEXT` (public-schema → auto-applies on deploy). |
| `layer1/builder.py` | `_PROFILE_COLS` += 4; `_load_athlete_profile` reads them into the performance/lifestyle dicts; `_empty_lifestyle()` defaults the 3 lifestyle fields to None. |
| `layer4/context.py` | `Layer1Lifestyle` += `sweat_rate_level`/`daily_hydration_baseline`/`sleep_consistency`; `Layer1Performance` += `body_weight_trend`; `RaceDayFueling` += `sweat_rate_modifier_applied=1.0`. |
| `layer2e/builder.py` | `_sweat_rate_modifier` + the fluid/sodium split in `_build_race_day_fueling`. |
| `routes/profile.py` | imports the 4 choice tuples; `save_nutrition` captures sweat/hydration/sleep-consistency (closed-set `_enum` validation); `edit` POST captures `body_weight_trend`; render context passes the 4 choice lists. |
| `templates/profile/edit.html` | §I Fuel-&-health tab: Sweat rate / Daily hydration / Sleep consistency selects; §A athlete tab: Recent weight trend select. |
| `tests/test_layer1_builder.py` | `_queue_andy` row + `_PROFILE_COL_NAMES` += 4 cols; +`test_v3_profile_fields_thread_through` + `test_v3_profile_fields_default_none_when_absent`. |
| `tests/test_layer2e.py` | extended `test_salt_tolerance_low_shrinks_na_band` (fluid now base 400-700, salt no longer scales it) + new `test_sweat_rate_high_scales_fluid_not_sodium`. |

**Scope:** 7 code + 2 test files — one coherent field-add change (the standard add-a-profile-field pipeline: `athlete`/`init_db`/route/template/`layer1`/`layer4`, plus the one V3-I-4 logic surface in `layer2e`). Within the spirit of the 5-file ceiling, same as the #304 Part B precedent (8 files, "one coherent reviewable change").

## 4. Verification

- Full `tests/` **4015 passed / 30 skipped** — no new failures; the 3 warnings pre-exist (#217).
- `ruff` on the 6 production files: **5 errors before == 5 after** (all pre-existing — `routes/profile.py` `E741 l`, etc. — left untouched per surgical-changes). My edits introduced **0** new errors.
- **No `layer0-apply` owed** — no `layer0` schema change. The 4 public-schema ALTERs auto-apply on the next Vercel deploy. Adding the 4 payload fields changes `layer1_hash` (keys every Layer-4 cache entry) → plan-gen cold-recomputes once next deploy; the V3-I-4 split changes the Layer-2E payload → its cache cold-recomputes once. Both expected under the partial-update model; safe (Andy is the only test athlete).

## 5. NEXT — DECIDED: Phase 1 continues with **#1067 (pack-load weighting)**

- **#1067 — pack-load weighting (per D1).** In `layer3b/builder.py` (~`:615`, the `pack_load_history` read) weight prior race experience above recent pack training; + a summary/edit/delete UX on the pack-load entry form (`routes/profile.py` + template; data via `pack_load_repo.py`). Its own PR off `main`.
- **Then #223 — pregnancy field (capture only).** Screening Q8/`PREGNANCY` as source of truth + an explicit capture field. **DEFER the `layer2e` HITL-gate half** (gates 1-4 are dead-stubbed `_emit_hitl_items` → `[]`; the gate change is stop-and-ask trigger #4). #223 is labelled `priority:low`/`icebox` — **re-confirm with Andy it's still wanted in Phase 1** before taking.
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
| 4 new columns in PROFILE_FIELDS | `athlete.py` | `grep -c "sweat_rate_level\|daily_hydration_baseline\|sleep_consistency\|body_weight_trend" athlete.py` → ≥4 |
| dietary tokens added | `athlete.py` | `grep "'low_carb', 'fat_adapted'" athlete.py` (present) |
| migrations present | `init_db.py` | `grep -c "ADD COLUMN IF NOT EXISTS sweat_rate_level\|daily_hydration_baseline\|sleep_consistency\|body_weight_trend" init_db.py` → 4 |
| fields threaded into payload | `layer1/builder.py` | `grep -c "sweat_rate_level\|sleep_consistency\|body_weight_trend" layer1/builder.py` → ≥3 |
| 2E split | `layer2e/builder.py` | `grep -c "_sweat_rate_modifier\|sweat_rate_modifier_applied" layer2e/builder.py` → 3; `grep 'band\["fluid_low"\] \* sweat_mod' layer2e/builder.py` (present) |
| regression tests | `tests/` | `test_v3_profile_fields_thread_through`, `test_sweat_rate_high_scales_fluid_not_sodium` |
| suite green | `tests/` | `python -m pytest tests/ -q` → 4015 passed / 30 skipped |

### §6.2 V3-I status (issue #257 — close on merge)

All 7 tracked V3-I items resolved: **V3-I-1/2/4/9/10 built** this session; **V3-I-7 already built** (athlete_supplements); **V3-I-3 dropped** (Andy). → #257 is **closeable as `completed`** when this lands.

### §6.3 DEFERRED — Rule #11 mechanical follow-up: onboarding spec §I → v7

The onboarding data spec wasn't bumped in this code PR (kept reviewable). To fold the now-built fields in, bump `aidstation-sources/specs/Athlete_Onboarding_Data_Spec_v6.md` → `_v7.md` (move v6 to `archive/superseded-specs/` per Rule #12) and **add these rows to the §I.1 "Core lifestyle fields" table** (after the `Caffeine Tolerance & Strategy` row):

```
| Sleep Consistency | Enum (Consistent / Mostly consistent / Variable / Highly variable) | 3 | Recovery-day placement refinement (variability beyond mean hours) | Self-report — #257 V3-I-1 |
| Daily Hydration Baseline | Enum (Low / Moderate / High) | 3 | Hydration-habit refinement | Self-report — #257 V3-I-9 |
```

**Add to §I.2 (Race-day fueling preferences):**
```
| Sweat Rate | Enum (Low / Moderate / High) | 2 | Layer 2E race-day FLUID band (split from Salt / Electrolyte Loss, which now drives sodium only — V3-I-4 resolves the v2 conflation noted in Section_I_Audit Fix-now #4) | Self-report — #257 V3-I-4 |
```

**Add to §A (Body) — a Body-weight Trend row:**
```
| Body-weight Trend (3 mo) | Enum (Stable / Gaining / Losing / Significant gain / Significant loss; significant = >5% / 3 mo) | 3 | Fueling-target accuracy | Self-report — #257 V3-I-10 |
```

And add to the §I.2 `Dietary Pattern` multi-select vocabulary note: `low_carb`, `fat_adapted` (macro axis distinct from `keto`/`paleo` — #257 V3-I-2).

**PR state:** none open. Pushed to `origin/claude/disclosures-payload-removal-p1-2v355b`; bookkeeping rides the same branch. Per the project operating model, **open the PR only on Andy's explicit go** (then `enable_pr_auto_merge` with **merge-commit** method). Issue #257 commented with the shipped status (close on merge).
