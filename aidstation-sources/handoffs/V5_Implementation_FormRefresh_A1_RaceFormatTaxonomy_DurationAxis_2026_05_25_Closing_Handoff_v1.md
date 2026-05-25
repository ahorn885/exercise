# FormRefresh A1 — Race-format taxonomy collapse + explicit duration axis — Closing Handoff

**Session:** Reconcile the conflated `race_format` enum into a purely structural 3-value axis and add the missing magnitude axis (`estimated_duration_hr` + `primary_metric`), on both the profile-edit and onboarding race forms. Plus an ordered runner that batches the owed Layer 0 Neon deploys.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_InjuryFormRefresh_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/injury-form-refresh-handoff-hBCmF`
**Status:** Two PRs. #159 (FormRefresh A1, **merged** to main) — ~14 substantive files, a one-session ceiling break authorized by Andy at the gate. #160 (this PR) — the layer0 runner + this handoff + the pointer update (bookkeeping). 1785 passed / 16 skipped.

---

## 1. Session-start verification (Rule #9)

This session continued an in-flight `/plan`-style design conversation (the FormRefresh slice-A race-form reconciliation), so it did not start cold; the formal `verify-handoff.sh` sweep was not re-run at the top. Retroactive spot-check of the predecessor (InjuryFormRefresh) §8 anchors:

| Claim | Anchor | Result |
|---|---|---|
| `athlete.BODY_PART_CONSTRAINTS` added | `grep -c BODY_PART_CONSTRAINTS athlete.py` → 1 | ✅ |
| Side `<select>` dropped from injury form | `grep -ci 'name="side"' templates/injuries/form.html` → 0 | ✅ |

**Reconciliation note:** clean on the spot-checks run. Note the rolling pointer's test count (1636) was stale on entry — the real baseline measured this session was **1784 passed / 16 skipped** (the InjuryFormRefresh + other 2026-05-25 work had landed since that measurement). Pointer test line refreshed in this session's CURRENT_STATE edit.

---

## 2. Session narrative

The driver: Andy's critique that `race_format`'s 4-value enum (`single_day` / `expedition_ar` / `stage_race` / `multi_day_ultra`) conflated **structure** with **sport** — `expedition_ar` = adventure-racing sport, `multi_day_ultra` = ultrarunning sport — and that there was no way to express a race's **magnitude by duration** (only `distance_km`), so every multi-day event got fed a coarse format-keyed duration estimate into Layer 2E.

`/plan`-mode gates (Andy's picks on the record):
- **Axis model = Option B**: collapse to a purely structural 3-value taxonomy `single_day` / `continuous_multi_day` / `stage_race`; sport lives on the existing `framework_sport` column.
- **Magnitude UX = primary-metric selector**: an explicit "this race is defined by [distance | duration]" toggle that shows the relevant input.
- **Scope = both surfaces** (profile edit + onboarding).
- **Sequencing = one big ceiling break** (~14 files in a single session) rather than the magnitude-first / enum-second split I proposed; Andy chose the monolith.

One decision I made and flagged rather than gated: **no `framework_sport` backfill** in the migration. Investigation showed `race_format` never sourced sport/discipline resolution (the orchestrator derives `framework_sport` from the column or `primary_sport`, never the format — `orchestrator.py:241-245`), so the collapse is information-preserving; and guessing a sport string during migration would *change* plan generation (and `"Ultrarunning"` isn't even a valid bridge sport — only `Ultramarathon (Trail)/(Road)`, `Adventure Racing` are). Left `framework_sport` untouched; it stays athlete-editable.

After #159 merged, Andy asked whether the owed migrations could be combined. Answer: they're **two channels** (public-schema `init_db._PG_MIGRATIONS` via `python init_db.py` vs. layer0 `etl/sources/*.sql` via `psql`), which can't merge — but the layer0 ones can run in one session. Shipped that as the #160 runner.

---

## 3. File-by-file edits

### PR #159 — FormRefresh A1 (merged to main)

#### 3.1 `init_db.py` (modified)
- CREATE TABLE `race_events` inline CHECK → 3 values (`init_db.py:1261`).
- Migration block (`init_db.py:1334-1355`): `ADD COLUMN IF NOT EXISTS estimated_duration_hr NUMERIC NULL CHECK (… > 0)`; `ADD COLUMN … primary_metric TEXT … CHECK (… IN ('distance','duration'))`; then the idempotent enum remap — `DROP CONSTRAINT IF EXISTS race_events_race_format_check` → `UPDATE … SET race_format='continuous_multi_day' WHERE race_format IN ('expedition_ar','multi_day_ultra')` → `ADD CONSTRAINT race_events_race_format_check CHECK (… 3 values)`. Order is load-bearing + re-run-safe.

#### 3.2 `race_events_repo.py` (modified)
- `VALID_RACE_FORMATS` → 3-tuple; new `VALID_PRIMARY_METRICS` (`:33-34`).
- `create_race_event` / `update_race_event`: new `estimated_duration_hr` + `primary_metric` kwargs, INSERT/UPDATE columns, and `primary_metric` validation.
- `load_race_event_payload` + `get_race_event`: SELECT + payload mapping for the two new columns.

#### 3.3 `layer4/context.py` (modified)
- `RaceFormat` Literal → 3 values (`:1137`); `Layer3BPayload.race_format` Literal → 3 values.
- `RaceEventPayload.estimated_duration_hr: Decimal | None = Field(default=None, gt=0)` + `primary_metric: Literal["distance","duration"] | None` (`:1187-1188`).

#### 3.4 `layer4/orchestrator.py` (modified)
- `_DURATION_HR_BY_RACE_FORMAT` → 3 keys (`single_day` 8 / `stage_race` 24 / `continuous_multi_day` 48) (`:125-133`).
- Duration precedence: `target_race_event.estimated_duration_hr` (cast to float) when non-None, else the format-keyed fallback, into `Layer2ETargetEvent.estimated_duration_hr`.

#### 3.5 `layer4/payload.py` (modified)
- `RaceWeekBrief.race_format` Literal → 3 values; `RacePlan.race_format` Literal → `["continuous_multi_day","stage_race"]`.

#### 3.6 `layer4/per_phase.py` (modified)
- `_TAPER_ANCHOR_BY_FORMAT` collapses the two AR/ultra keys into `continuous_multi_day`; D7 prose updated; per-phase race-event context now renders `Estimated duration:`.

#### 3.7 `layer4/race_week_brief.py` (modified)
- Brief tool-output JSON schema enum → 3 values; race_plan schema enum → 2 values; `_MULTI_DAY_FORMATS` + `_validate_inputs` valid_formats sets → new values; brief context renders `Estimated duration:` + `Primary metric:` (the latter cues pace/segment language).

#### 3.8 `layer4/validator.py` (modified)
- Rule 18 `_CONTINGENCY_ANCHORS_PER_FORMAT` re-derived (`:166-180`): `continuous_multi_day` = `gi/hydration/mechanical/cumulative_fatigue/sleep_dep`. **Behavior change:** the old `expedition_ar`-only `nav` + `weather` anchors are dropped from the format axis (discipline/environment concerns belong to a future `navigation_required` + Layer 2B terrain slice, not the structural format).

#### 3.9 `routes/race_events.py` + `routes/onboarding.py` (modified)
- `_parse_estimated_duration_hr` (coerces ≤0 / non-numeric → None) + `_parse_primary_metric` (closed-set → None). Wired into create/update on both surfaces. Invalidation: `estimated_duration_hr` change → periodization-grade (feeds 2E → brief + plans); `primary_metric` change → brief-only. Onboarding imports the two parsers from `routes.race_events`.

#### 3.10 `templates/profile/race_event_edit.html` + `templates/onboarding/target_race.html` (modified)
- Format dropdown help-copy rewritten to describe the **structural** axis. New primary-metric `<select>` + a duration input, each distance/duration block tagged `data-metric-field`; a CSP-nonced `<script>` toggles which shows. Hidden input keeps its value so a toggle is non-destructive (lossless round-trip).

### PR #160 — Layer 0 runner (this PR)

#### 3.11 `etl/sources/run_owed_layer0_migrations.sql` (new, 50 lines)
Ordered `psql` runner (`\set ON_ERROR_STOP on` + `\ir` so includes resolve relative to the runner's own dir, CWD-independent; no global transaction — each script self-manages). Applies, in dependency order: PR #156 `migrate_disciplines_add_primary_movement_v1.sql` (schema; hard prereq) → K3 `populate_equipment_items_K3_additions.sql` → the three D-74 idempotency re-runs. Deliberately pulls the live `etl/sources/` terrain_gap_rules copy, not the stale `migrations/` one (D-76 footgun).

---

## 4. Code / tests

Baseline **1784 passed / 16 skipped** → **1785 passed / 16 skipped** after #159 (net +1).

Test-fixture migration across 9 suites (old enum values → `continuous_multi_day`): `test_race_events_repo` (fixture `_race_row` + closed-set test rewritten `_closed_4_set`→`_closed_3_set` + positional-INSERT indices shifted +2 for the two new columns), `test_layer4_orchestrator` (`_queue_target_race_event` gains the two columns), `test_layer4_race_week_brief`, `test_layer4_payload`, `test_layer4_validator`, `test_layer3b_builder`, `test_layer3b_smoke`, `test_layer3_cached_wrappers`, `test_onboarding_race_events`, `test_routes_race_events`.

New orchestrator tests (`test_layer4_orchestrator.py`): `test_continuous_multi_day_format_uses_48h_duration_fallback` + `test_explicit_estimated_duration_hr_overrides_format_fallback` — lock the column→fallback precedence. Validator rule-18 `test_contingency_anchors_covered_no_fire` updated to the new required-anchor set (adds `sleep_dep`).

---

## 5. Manual §5.0 verification steps

Owed (no sandbox runtime / no `DATABASE_URL` here):
1. Profile → Race events → edit a race: confirm the **Primary metric** selector toggles the Distance ↔ Estimated duration inputs; save with `duration` picked and a value; reload and confirm it round-trips. Repeat on **onboarding** `/onboarding/target-race`.
2. Confirm the format dropdown shows the 3 structural values with the new help copy.
3. After running the migrations (below), set a `continuous_multi_day` target with an explicit duration and confirm the race-week brief / plan reflect it (Layer 2E fueling tiers).

Append to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" if not walked this cycle.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Run the two owed migration channels on Neon** (both Andy's hands — no `DATABASE_URL` in the build container), then the manual UI eyeball:
- Public schema: `python init_db.py` — applies the FormRefresh A1 `race_events` columns + enum remap (idempotent).
- Layer 0: `psql "$DATABASE_URL" -f etl/sources/run_owed_layer0_migrations.sql` — PR #156 (hard prereq) + K3 + D-74.

### 6.2 Alternative pivots
- **Form-feedback slice A, remainder.** This session closed item 1+2 (distance-or-duration metric + format/`framework_sport` reconciliation). Still open and needing its own plan-mode design (Trigger #3): drop aid-stations count + derive fueling cadence from route locales (Layer 2E); mandatory-gear → pack-weight/portage.
- **Form-feedback slice C** — schedule inference (Layer 1 derivation). Needs plan-mode design.
- **`navigation_required` + terrain-driven contingency anchors** — the home for the `nav`/`weather` anchors removed from the validator's format axis this session. `navigation_required` already exists as a Layer 3B input (`bool | None`, unwired); promoting it to a `race_events` column is the slice.

### 6.3 Operating notes for next session
1. `CLAUDE.md` — stable rules (read first, Rule #13).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | `race_format` → 3 structural values (`single_day`/`continuous_multi_day`/`stage_race`); sport stays on `framework_sport` | Andy at gate | Untangles structure from sport/discipline; the axis is now purely structural. |
| 2 | Magnitude via explicit primary-metric selector + `estimated_duration_hr` column | Andy at gate | Lets duration-defined races (rogaines, expeditions) be sized directly instead of via a coarse format estimate. |
| 3 | Ship on both surfaces (profile + onboarding) | Andy at gate | Parity; onboarding writes the target row too. |
| 4 | One-session ceiling break (~14 files) over a magnitude-first/enum-second split | Andy at gate | Andy chose the monolith; authorized. |
| 5 | **No `framework_sport` backfill** in the migration | this agent (flagged; accepted via merge) | `race_format` never sourced sport resolution → collapse is information-preserving; a guessed sport string would change plan gen and may not be a valid bridge sport. |
| 6 | Validator `nav`/`weather` anchors removed from the format axis | this agent (within authorized scope) | Discipline/environment concerns, not structural; future `navigation_required` + terrain slice owns them. |
| 7 | Prior-session `CURRENT_STATE.md` edit committed as-is | Andy | It was the injury-form pointer update left uncommitted; landed unchanged. |
| 8 | Layer 0 owed deploys → single `psql` runner; channels not merged | Andy approved building | Two distinct schema+runner channels; only the layer0 set batches. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `race_events_repo.py:33` `VALID_RACE_FORMATS = ("single_day", "continuous_multi_day", "stage_race")` | ✅ grep |
| `layer4/context.py:1137` `RaceFormat = Literal[…3 values]`; `:1187-1188` `estimated_duration_hr` + `primary_metric` | ✅ grep |
| `init_db.py:1334-1355` two ADD COLUMN + the DROP/UPDATE/ADD CONSTRAINT remap trio | ✅ grep |
| `layer4/orchestrator.py:132` `"continuous_multi_day": 48.0` + duration precedence | ✅ grep |
| `layer4/validator.py:166-180` `_CONTINGENCY_ANCHORS_PER_FORMAT` 3 keys, `continuous_multi_day` incl. `sleep_dep`, no `nav`/`weather` | ✅ grep |
| `etl/sources/run_owed_layer0_migrations.sql` exists (50 lines) | ✅ wc |
| No `expedition_ar`/`multi_day_ultra` in runtime except the migration UPDATE + explanatory comments | ✅ grep |
| Full suite | ✅ 1785 passed / 16 skipped |
| Working tree clean after the #160 commits | ✅ git status |

---

## 9. Files shipped this session

**Substantive (PR #159 — ~14 files; ceiling break authorized at the gate):**
1. `init_db.py`
2. `race_events_repo.py`
3. `layer4/context.py`
4. `layer4/orchestrator.py`
5. `layer4/payload.py`
6. `layer4/per_phase.py`
7. `layer4/race_week_brief.py`
8. `layer4/validator.py`
9. `routes/race_events.py`
10. `routes/onboarding.py`
11. `templates/profile/race_event_edit.html`
12. `templates/onboarding/target_race.html`
13. (tests) 9 suites migrated + 2 new orchestrator tests
14. (PR #160) `etl/sources/run_owed_layer0_migrations.sql`

**Bookkeeping:**
- This handoff; `CURRENT_STATE.md` pointer update (both on PR #160).

---

## 10. Carry-forward updates

None this session beyond the manual §5.0 steps in §5 (append to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" if not walked).

---

**End of handoff.**
