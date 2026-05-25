# FormRefresh C — schedule simplification (infer long day + rest days) — Closing Handoff

**Session:** Form-feedback **Slice C** (the last of the numbered batch, item 5: "schedule simplification (infer long day + rest days)"). Andy first asked to do the owed ETL/migration; that stayed blocked (no `DATABASE_URL` in the container — see §5) so he picked Slice C instead. Designed + ratified at AskUserQuestion gates (Trigger #1/#3), then implemented as one authorized over-ceiling slice.
**Date:** 2026-05-25
**Predecessor handoff:** `V5_Implementation_FormRefresh_A2_DropAidStations_RouteLocalesAllTypes_Portage_2026_05_25_Closing_Handoff_v1.md`
**Branch:** `claude/aid-stations-etl-migration-YdpaG` (harness-pinned to the ETL task; scope pivoted to Slice C at Andy's pick — kept the branch name since the same branch already carries the owed A1/A2 migrations and Slice C adds one more to that same owed `init_db.py` run)
**Status:** Implementation complete on-branch; draft PR opened; not yet merged. 6 substantive code files + 3 test suites + 3 spec docs. Container suite green. **Owed Neon deploy stacks onto A1/A2** (the §G column drops + the window CHECK bump are part of the same idempotent `python init_db.py`).

---

## 1. Session-start verification (Rule #9)

This session picked up after Andy redirected from the owed migration. Rather than the `verify-handoff.sh` anchor sweep (which checks the *previous* A2 handoff — its anchors were spot-checked clean: `init_db.py` `DROP COLUMN IF EXISTS aid_stations` present, `layer2e/builder.py _emit_hitl_items` is `return []`, both race-form templates aid-stations-free), the load-bearing reconciliation here was **mapping the as-built schedule surface** before designing Slice C. Confirmed via a thorough Explore pass + direct reads:

- The v5 §G **per-day-window model is fully shipped** (`daily_availability_windows` table exists in `init_db.py`; `_schedule_form.html` captures per-day `enabled/start/duration` + doubles second window). Slice C is therefore a clean "remove two inputs + infer them," not entangled with a larger §G rewrite.
- The explicit `long_session_days` + `preferred_rest_days` pickers sat *alongside* the windows as redundant inputs. **No Layer 4 validator rule and no prompt body reads them** (grep-verified across `layer4/`, `routes/`, builders) — only the windows themselves (enabled flags + durations) drive `_rule_schedule_violation` / `_rule_daily_window_fit`. So inferring them away is functionally safe (typed-contract + form change only; cache hash shifts, no users).

Test-environment: fresh web container, deps not pre-installed; installed into `/tmp/venv` via `pip install -r requirements.txt pytest`. Suite collects + runs clean there.

---

## 2. Session narrative

Andy: "let's work. I still haven't been able to do the etl / migration." The owed Neon migrations (A1 race_events remap + A2 `aid_stations` drop + the layer0 runner) need a `DATABASE_URL` the build container doesn't have. Surfaced the exact state (code all present on this branch, scripts verified idempotent, the only blocker is DB credentials) and offered to run it if he pasted a Neon URL, give him a one-shot runbook, or diagnose his local blocker. **Andy: skip the migration this session, work on something else.** Offered the open backlog; he picked **Slice C — schedule inference**.

Per Trigger #1/#3 I designed before building. Research reframed the scope: the v5 §G design (`Onboarding_D61_Design_v1.md` §7.3) had *kept* Long Session Available / Doubles Feasible / Preferred Rest Day(s) as standalone profile fields — so Slice C is a step *beyond* what was specced. Presented the design + three forks at an AskUserQuestion gate. Andy's picks (§7) re-scoped the long-session half from "infer the day, keep the capacity toggle" to **drop the whole block** (the longest enabled window *is* the long session; raise the window cap so it fits), kept the rest-day inference, and authorized one over-ceiling slice. Implemented, tested green, wrote the v6 spec + Layer1_Spec edits + the D-61 supersession banner.

---

## 3. File-by-file edits

### Substantive code

#### 3.1 `templates/onboarding/_schedule_form.html`
- Removed the entire **"Long session"** block (the `long_session_available` checkbox + `long_session_days` day-checkbox grid + `long_session_max_hr` select) and the **"Preferred rest day(s)"** block. Daily-windows intro copy updated ("between 30 and 720"; unchecked days are rest; longest enabled window = long session). Primary-duration `<input max>` 360→720 (second-window duration input left at 360). The JS (`recomputeTotal` / second-window visibility) was untouched — it never referenced the removed fields.

#### 3.2 `templates/onboarding/schedule.html`
- Docstring updated (no longer "three orthogonal capacity toggles"; notes the long-day + rest inference).

#### 3.3 `routes/onboarding.py`
- Dropped `LONG_SESSION_MAX_HR_CHOICES` from the `athlete` import; deleted the now-dead `_filter_day_tokens` + `_split_csv_days` helpers; removed the long-session + rest-day parsing and the dead `enabled_day_tokens` accumulator from `_parse_schedule_form` (now returns `profile_updates = {'doubles_feasible': doubles}`); primary-window `_parse_int(max_=...)` 360→720 + error text "30–720"; trimmed the GET `schedule()` template context to `days` + `doubles_feasible` + `doubles_choices` + `post_step3b_target`. `schedule_save` docstring updated.

#### 3.4 `routes/profile.py`
- Dropped `DAY_TOKENS` / `DAY_LABELS` / `LONG_SESSION_MAX_HR_CHOICES` from the `athlete` import; deleted the dead `_split_csv_day_tokens` helper; trimmed the `/profile?tab=schedule` GET context (dropped `long_*` / `preferred_rest_days` / `day_tokens` / `day_labels` / `long_session_max_hr_choices`); `save_schedule` docstring updated. (`_parse_schedule_form` is still lazy-imported from `routes.onboarding` and now writes only `doubles_feasible`.)

#### 3.5 `athlete.py`
- `PROFILE_FIELDS`: removed `long_session_available`, `long_session_days`, `long_session_max_hr`, `preferred_rest_days` (kept `doubles_feasible`); comment rewritten. Removed the `LONG_SESSION_MAX_HR_CHOICES` constant. (`get_athlete_profile` SELECTs `PROFILE_FIELDS`, so dropping them here is what makes the post-`DROP COLUMN` read path work; `upsert_athlete_profile` filters kwargs against `PROFILE_FIELDS`.)

#### 3.6 `layer1/builder.py`
- `_PROFILE_COLS`: removed the 4 columns (kept `doubles_feasible`). `_load_athlete_profile` availability_scalars + `_empty_availability_scalars` reduced to `{'doubles_feasible': ...}`. `_load_daily_windows` no longer reads the long-session/rest scalars or builds `preferred_rest_days_set`; the `DailyAvailabilityWindow` construction drops `long_session_available` / `long_session_max_duration` / `preferred_rest_day`. Removed the now-unused `_DAY_TOKENS` module constant (`_DAY_LABELS` stays — still maps dow→label).

#### 3.7 `layer4/context.py`
- `DailyAvailabilityWindow`: removed `long_session_available`, `long_session_max_duration`, `preferred_rest_day`; **`window_duration` cap `le=360`→`le=720`** (primary window now carries the long session); `second_window_duration` left at `le=360`. The two `@model_validator`s (enabled invariants + second-window pairing) reference only surviving fields — untouched.
- `Layer1Availability`: reduced to a single `doubles_feasible` field; comment rewritten.

#### 3.8 `init_db.py`
- Both `athlete_profile` CREATE TABLE definitions (the `PG_SCHEMA` inline block + the compact migration-list copy) reduced to `doubles_feasible TEXT` for the §G scalars.
- `daily_availability_windows` CREATE: the inline duration CHECK is now **named** `daily_availability_windows_duration_bound` with bound `30 AND 720` (fresh DBs get 720 directly).
- Migration list: kept the `doubles_feasible` `ADD COLUMN IF NOT EXISTS`; added 4× `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS <field>` (idempotent; no-op on fresh DBs); added a `DO $$ … $$` block that migrates a **deployed** `daily_availability_windows` whose inline CHECK still pins 360 — it drops the anonymous CHECK matched by its `360` literal (deliberately matched by literal so the enabled/window-pairing CHECK, which *also* references `window_duration_min` but contains no `360`, is left intact) and adds the named 720 bound, guarded so re-runs are no-ops. (`init_postgres()` runs migrations with no params via raw `cur.execute(stmt)`, so the `%I` in the PL/pgSQL `format()` is safe — psycopg2 only `%`-interpolates when `vars` is passed.)

### Test suites (3)
- `tests/test_layer1_builder.py` — `_queue_andy` fixture drops the 4 removed columns; empty-default test drops `w.preferred_rest_day` + flips `availability.long_session_available` → `availability.doubles_feasible is None`; `test_daily_windows_denormalize_per_week_capacity` renamed **`test_daily_windows_denormalize_doubles_and_infer_rest`** (asserts `doubles_feasible` denorm + Monday `enabled is False` as the inferred rest day, drops the `long_session_max_duration` / `preferred_rest_day` asserts); CSV-edge test + `_PROFILE_COL_NAMES` mirror de-referenced the 4 columns.
- `tests/test_layer4_context.py` — removed `preferred_rest_day` from the `DailyAvailabilityWindow` happy-path + forbid-extra cases.
- `tests/test_layer4_validator.py` — removed `preferred_rest_day` from the `_window(...)` builder helper (both branches).

### Spec docs (3)
- **NEW `Athlete_Onboarding_Data_Spec_v6.md`** (full copy of v5 per Rule #12) — "What changed in v6 vs v5" header block; §G.1 drops the Long Session + Preferred Rest rows + Daily Windows duration range 360→720; §G.2 adds "Weekly long session" + "Rest days" as derived values; §G.3 removes the long-session window-override bullet + the long-session-subset bullet; §M.1 removes the "Athlete updates Long Session Available" lifecycle trigger (folded the re-derive note into the `daily_availability_windows` trigger).
- `Layer1_Spec.md` (unversioned consolidation — in-place) — §5.2 csv list drops the 2 day-token columns; §5.4 retitled to `doubles_feasible` denormalization + a Slice-C note; §7 payload tree `availability` sub-tree reduced to `doubles_feasible`; §12 test-scenario row re-pointed at the renamed test.
- `Onboarding_D61_Design_v1.md` (in-place supersession banner under the header — matches the A2 Layer2E "removed gate" annotation precedent; not version-bumped since it's a closed design-wave artifact) pointing §3.1/§7.3 at the v6 spec + Layer1_Spec §5.4.

---

## 4. Code / tests

Container suite: **1641 passed / 16 skipped** (`/tmp/venv`). **Net test delta: 0** — one denormalize test renamed + re-pointed at inferred-rest semantics; no tests added or removed (assertions on dropped fields were deleted in place). All suites collect with no errors.

---

## 5. Manual §5.0 verification steps (owed — Andy's hands)

Appended to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" as the **FormRefresh Slice C** entry (4 steps). Summary:
1. **Migration:** `python init_db.py` — `\d athlete_profile` no longer lists the 4 §G columns (only `doubles_feasible` survives); `\d daily_availability_windows` shows `window_duration_min` CHECK bounding `30..720` (named `daily_availability_windows_duration_bound`). This is the **same single idempotent run** that's owed for A1 + A2.
2. `/onboarding/schedule` (Step 6): the "Long session" + "Preferred rest day(s)" blocks are gone; duration input accepts up to 720; intro copy notes unchecked = rest + longest window = long session.
3. Enter a window > 360 (e.g. Sat 480) and Save — persists with no "30–360" flash; Doubles=Occasionally still saves a 360-capped second window.
4. `/profile?tab=schedule` round-trips; `build_layer1_payload` still constructs (`availability` now carries only `doubles_feasible`; rest = disabled `daily_availability_windows` rows).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Run the owed Neon deploys** (still Andy's hands; now four channels' worth of public-schema changes in one idempotent `python init_db.py`: A1 race_events remap + A2 `aid_stations` drop + **Slice C §G column drops + the `daily_availability_windows` 720 CHECK bump**) **plus** the layer0 `etl/sources/run_owed_layer0_migrations.sql` runner (PR #156 `primary_movement` is a HARD Layer-2A prereq). Then the A1 + A2 + Slice-C manual UI eyeballs. The container has no `DATABASE_URL`; if Andy pastes a Neon dev-branch URL, the next agent can `pip install psycopg2-binary` and run both channels here (PyPI is reachable).

### 6.2 Open pivots (the numbered form-feedback batch is now fully closed)
- **`navigation_required` → `race_events` column** — promote the unwired Layer 3B input (home for the nav/weather contingency anchors removed in A1). Cross-layer (Trigger #3); needs plan-mode design.
- **Spec narrative sweep** — per-layer specs still cite pre-R6 discipline ids in prose; D-61 design now has a partial-supersession banner but other design-wave docs may carry stale §G claims.
- **Plan-gen long-session placement** — Slice C made the long session "the longest enabled window," but no Layer 4 plan-gen node *consumes* that yet (it's a future plan-gen concern; the windows + durations are all present in the payload).
- **Manual §5.0 real-LLM walk** — accumulated scenarios in `CARRY_FORWARD.md`.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules (read first).
2. `CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep; reconcile any ❌ first.
6. **Test env:** deps not pre-installed in fresh web containers — `pip install -r requirements.txt pytest` into a venv.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | **Drop the whole Long Session block** (available / days / max_hr), not just the day-picker | Andy at gate | The longest enabled window *is* the long session. Removes the redundant capacity input entirely. |
| 2 | **Raise the primary daily-window cap 360→720 min** (6→12 h) | Andy at gate (implied by #1) | The window now carries the long session; the dropped `long_session_max_hr` enum topped out at "8+", so the window must reach expedition length. Second (doubles) window stays 360. |
| 3 | **Infer rest days from `enabled=FALSE`**; drop `preferred_rest_days` | Andy at gate | A disabled day already is a rest day to plan-gen; the soft "prefer to rest among available days" signal was unused by any rule. |
| 4 | **`DROP COLUMN`** the 4 §G scalars (not leave-nullable) | this agent (within scope; A2 precedent) | No real users; clean removal; reversible via re-add in git. |
| 5 | **One over-ceiling slice** (6 code + 3 tests + 3 specs) | Andy at gate | One coherent mechanical simplification threaded through its consumers (the A2 pattern). |
| 6 | D-61 design doc gets an **in-place supersession banner**, not a v2 bump | this agent | Closed design-wave artifact; a one-line forward-pointer matches the A2 Layer2E annotation precedent and avoids needless file proliferation. The canonical contract lives in the v6 spec + Layer1_Spec. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `grep -c long_session athlete.py` → 0; `PROFILE_FIELDS` has `doubles_feasible`, not the 4 dropped | ✅ |
| `grep -n "le=720" layer4/context.py` → `DailyAvailabilityWindow.window_duration`; `Layer1Availability` body = only `doubles_feasible` | ✅ |
| `init_db.py` has 4× `ALTER TABLE athlete_profile DROP COLUMN IF EXISTS long_session_*/preferred_rest_days` + the named `daily_availability_windows_duration_bound` CHECK (720) + the `DO $$` migration | ✅ |
| `_schedule_form.html` — no `long_session`/`preferred_rest` inputs; primary duration `max="720"` | ✅ grep |
| `layer1/builder._load_daily_windows` builds `DailyAvailabilityWindow` without long-session/rest kwargs | ✅ |
| No `long_session`/`preferred_rest` refs in non-test/non-doc code (only explanatory comments remain) | ✅ grep |
| Templates parse (Jinja) + edited modules `py_compile` | ✅ |
| Full suite | ✅ 1641 passed / 16 skipped (`/tmp/venv`, this container) |
| `Athlete_Onboarding_Data_Spec_v6.md` exists; §G.1 Long Session + Preferred Rest rows removed; duration 360→720 | ✅ |
| Working tree: only the intended files | ✅ git status |

---

## 9. Files shipped this session

**Substantive code (6):** `templates/onboarding/_schedule_form.html`, `templates/onboarding/schedule.html`, `routes/onboarding.py`, `routes/profile.py`, `athlete.py`, `layer1/builder.py`, `layer4/context.py`, `init_db.py`. *(Counting the two templates + the schema file, this is 8 file touches but a single mechanical field-deletion threaded through its consumers — authorized over-ceiling at the gate, A2 pattern.)*
**Tests (3):** `tests/test_layer1_builder.py`, `tests/test_layer4_context.py`, `tests/test_layer4_validator.py`.
**Specs (3):** `Athlete_Onboarding_Data_Spec_v6.md` (new), `Layer1_Spec.md` (in-place), `Onboarding_D61_Design_v1.md` (in-place banner).
**Bookkeeping:** this handoff; `CURRENT_STATE.md` pointer + open-moves + tests; `CARRY_FORWARD.md` §5.0 entry.

---

## 10. Carry-forward updates

- New Manual §5.0 entry (FormRefresh Slice C UI + migration eyeball) appended to `CARRY_FORWARD.md`.
- The numbered form-feedback batch (items 1–6) is now **fully closed**: 1+2 (A1 format/duration), 3 (A2 aid-stations/portage), 4+6 (injury-form refresh), 5 (this slice).
- No prior §5.0 scenario entered `long_session_*`/`preferred_rest_days`, so nothing was superseded by this change.

---

**End of handoff.**
