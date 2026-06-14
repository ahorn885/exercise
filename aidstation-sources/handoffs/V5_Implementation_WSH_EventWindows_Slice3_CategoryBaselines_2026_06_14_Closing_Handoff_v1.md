# V5 Implementation — WS-H: Event Windows — Slice 3: category equipment baselines (F8) — Closing Handoff

**Session:** Built **Slice 3** of the Event-Windows arc — category equipment baselines (design §F8). A not-yet-logged locale (an away destination created inline per Slice 2b, or a cold home gym) now **assumes** an authored, per-category equipment + terrain baseline until the athlete logs actuals on arrival → which then refreshes the window (the arrival-regen loop). This is **what makes "away" useful cold** — before, a never-logged destination resolved empty and degraded every discipline to near-strength.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSH_EventWindows_Slice2b_InlineCreate_2026_06_14_Closing_Handoff_v1.md` (Slice 2b inline-create, PR #601 merged + live).
**Branch:** `claude/v5-wsh-eventwindows-inline-create-rt69cq` (PR [#603](https://github.com/ahorn885/exercise/pull/603) — **OPEN, not merged**). *(Harness-pinned branch name reads "inline-create" / Slice 2b; actual scope is Slice 3. Kept per the session's explicit "never push to a different branch" instruction rather than renamed.)*
**Spec/arc:** `designs/Event_Windows_Design_v1.md` §F8 + §6 (Slice 3). **North-star:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2 WS-H. **Epic:** [#581](https://github.com/ahorn885/exercise/issues/581).

---

## 1. Session-start verification (Rule #9)

Ran `./scripts/verify-handoff.sh` against the Slice-2b handoff — all green, tree clean, branch correct, §8 anchors present on disk (the `event_windows.html` inline-create link; `new_locale`/`_stash_return_to`/`_locale_flow_redirect`; the render-smoke test). No drift — Slice 2b is genuinely merged + live.

---

## 2. Decisions (Andy-ratified in-session, 2026-06-14)

Slice 3 trips **Trigger #2** (the baseline *contents* are reference data) + **Trigger #3** (new layer0 table) + **Trigger #1** (the overlay wording). Stopped and got sign-off before building. The decisions, in the order they were settled:

1. **Storage / authoring model** — Andy initially said "wherever they live now, do not create new values," then corrected: *"the baselines need to be created… single baseline that we edit."* → **one authored, editable baseline per logical category** (a layer0 seed table we maintain), **not** a crowd aggregate.
2. **Scope of "single baseline"** — **one authored list per category**, for §F8's set, which became **4** once pools were added: **commercial / hotel / climbing / pool**.
3. **Transition** — **replace** (the baseline applies only when the locale has zero logged equipment / zero logged terrain; any logged value fully wins).
4. **Apply scope** — **universal** (home + away). The away env already resolves through `cluster_equipment_by_locale` / `cluster_terrain_by_locale`, so this needed **no away-path change**; a cold home locale benefits too.
5. **Pools** — added a **4th** (pool) baseline; it is **terrain-only** (there is no `Pool` equipment row — swimming is terrain-gated by `TRN-008`).
6. **Overlay mark (Trigger #1)** — yes: a cold away segment shows a "log actuals on arrival to refine this window" note.
7. **Contents (Trigger #2)** — ratified item-by-item (see §3). Two name corrections surfaced during reconciliation (`Rowing machine`→`Rowing ergometer`; `Pool` is terrain not equipment) and one self-inflicted scare (`bosu` "missing" was a grep bug — `BOSU ball` is canonical under `Plyo, Power & Stability`; **no vocabulary drift**).

---

## 3. The four baselines (ratified contents)

Keyed by **logical category**; the 5 gym + 2 pool `MANUAL_CATEGORIES` slugs collapse to these 4 via `locations._CATEGORY_BASELINE_KEY`.

| Baseline (slugs) | Equipment (exact `equipment_items` canonical names) | Terrain |
|---|---|---|
| **commercial** (`commercial_chain_gym`, `independent_gym`) | Dip bars, Foam roller, Pull-up bar, Resistance band, TRX / suspension trainer, Yoga mat, Barbell, Bench, Dumbbell, EZ curl bar, Kettlebell, Squat rack, Weight plates, Elliptical, Rowing ergometer, Stationary bike, Treadmill, Cable machine, Chest press machine, Lat pulldown machine, Leg press machine, Seated row machine, Smith machine, BOSU ball, Battle ropes, Medicine ball, Plyo box, Stability ball | TRN-001, TRN-016 |
| **hotel** (`hotel_gym`) | Dumbbell, Treadmill, Stationary bike, Elliptical, Bench, Yoga mat, Stability ball | TRN-001, TRN-016 |
| **climbing** (`climbing_gym_chain`, `climbing_gym_indie`) | Treadwall, Hangboard, Pull-up bar, Campus board | TRN-001, TRN-016, TRN-014 |
| **pool** (`pool_indoor`, `pool_outdoor`) | *(terrain-only)* | TRN-008 |

Terrain ids: `TRN-001` Road/Paved, `TRN-016` Indoor/Gym, `TRN-014` Climbing Gym, `TRN-008` Pool.

---

## 4. Implementation

- **`etl/migrations/layer0/0005_seed_location_category_baseline.sql`** (NEW) — `CREATE TABLE layer0.location_category_equipment_baseline (category, equipment_tags TEXT[], terrain_ids TEXT[], etl_version, etl_run_at, superseded_at)` + the 4 seed rows + a verify block. **Verify block:** row-count (=4, hard) + terrain-id FK-check against `terrain_types` (hard) + equipment-tag FK-check against `equipment_items` (**NOTICE, see §6**).
- **`locations.py`** — `load_category_baselines` (`try/except`→`{}` if table absent; reuses `_coerce_terrain_ids` as the generic TEXT[] coercer); `_CATEGORY_BASELINE_KEY` (5+2→4) + `_BASELINE_DISPLAY`; `_category_baseline` + `_locale_category` (its own query so the existing `gym_profile_id`/`locale_terrain_ids` SELECTs are unchanged); `locale_assumed_baseline_display` (the overlay flag — cold = no logged equipment AND no logged terrain); and the substitution inside `cluster_equipment_by_locale` + `cluster_terrain_by_locale`, **gated behind `if baselines and not <logged set>`** so a baseline-unaware caller (pre-migration, or a SQL-shape test fake) is byte-identical. Rule #15: each substitution logs `assumed_baseline=… (category=… no logged equipment/terrain)`.
- **`layer4/orchestrator.py`** — registered `"location_category_equipment_baseline": "0C"` in `_LAYER0_TABLE_FAMILY`; in the away branch, `assumed_baseline = locations.locale_assumed_baseline_display(...)` → passed to `EventWindowSegment(assumed_baseline_category=…)` (+ folded into the Rule #15 `_away_dbg` line). **No resolution change** — the away cluster's equipment/terrain already flow through the two cluster fns, which now substitute the baseline for the cold destination.
- **`layer4/session_feasibility.py`** — `EventWindowSegment.assumed_baseline_category: str | None = None`.
- **`layer4/per_phase.py`** — `_event_window_label` appends the Trigger-#1 note when `segment.assumed_baseline_category` is set: *`[Equipment/terrain at "<dest>" is assumed from the standard <category> baseline — log the gym's actual equipment on arrival to refine the plan for this window.]`*

**Cache:** the table is in `_LAYER0_TABLE_FAMILY` (0C), and `etl_version_set` is folded into `plan_create_key`/`plan_refresh_key`, so a baseline edit (supersede + bumped `etl_version`) busts the affected plan caches (home **and** away). For a *home* cold locale the resolved `terrain_feasibility` hash already captures it; for *away* the digest is the path (away feasibility is in `compute_event_windows_hash`, which intentionally doesn't hash resolved equipment).

**5 substantive files** (migration, `locations.py`, `orchestrator.py`, `session_feasibility.py`, `per_phase.py`) — at the ceiling; tests not counted.

---

## 5. Tests

- **`tests/test_layer4_location_baselines.py`** (NEW, 19 cases) — `load_category_baselines` parse + absent-table-degrades; the equipment substitution (cold→assume, logged-wins, non-baseline-category stays empty, pool-has-no-equipment, absent-table-no-op); the terrain substitution (cold→assume, pool→TRN-008, logged-wins); `locale_assumed_baseline_display` (cold→label, equipment-logged→None, terrain-logged→None, non-baseline-category→None, absent-table→None); and a **drift guard** asserting `_CATEGORY_BASELINE_KEY` covers exactly the non-residential, non-park `MANUAL_CATEGORIES` slugs.
- **`tests/test_layer4_event_windows.py`** +2 — the overlay note renders on a cold away segment / is absent when the destination is logged.
- **`tests/test_layer4_orchestrator.py`** +1 — `_LAYER0_TABLE_FAMILY` includes the new table (0C).

**Full suite: 2452 passed / 30 skipped.** Env: `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, full `tests/`.

**Layer-0 gate reproduced locally → PASS** (schema + genesis v1.6.7 + migrations 0001–0005 + `validate_layer0`), as `pgrunner` per the CARRY_FORWARD recipe.

---

## 6. CI + the post-apply token correction

The first push **failed** the Layer-0 integrity gate on a hard equipment FK-check: three seed tokens — `Bench press rack`, `Climbing Wall`, `Crash pad` — were absent from the gate's frozen genesis snapshot. They turned out to be **wrong/renamed canonical names** I pulled from stale `etl/sources` files: the live `layer0.equipment_items` vocabulary (confirmed by Andy pasting it on the Neon apply, Rule #14) has **no** such tokens — they were superseded/renamed in a later vocab pass. So the fix was a **contents correction**, not a CI hack:

- **hotel:** `Bench press rack` → **`Bench`**.
- **climbing:** `Climbing Wall` → **`Treadwall`** (the live "Grip & Climbing" wall token, Andy's call); `Crash pad` **dropped** (no live token; the boulder mats are the venue = the `TRN-014 Climbing Gym` terrain already in the baseline); **`Campus board`** added (Andy). → `{Treadwall, Hangboard, Pull-up bar, Campus board}`.
- Climbing-gym indoor feasibility rests on **`TRN-014 Climbing Gym`** in the baseline's terrain (Andy's "make sure the terrain is mapped to climbing gyms too" — it already was).

All corrected tokens are in both the live vocabulary **and** the CI genesis, so the equipment FK-check is **hard (`RAISE EXCEPTION`)** again — the temporary NOTICE softening was reverted once the seed was correct. Full gate reproduced locally → PASS. **Neon:** the first apply committed the *old* (wrong) tokens; corrected in place via two `UPDATE`s (hotel + climbing `equipment_tags`) — see §7. *(Sidebar: the live vocab is cleaner-cased than the v1.6.7 genesis dump — `Pinch block`, `Wrist roller`, `Glute ham developer (GHD)` — i.e. genesis lags live in general; not relevant to this slice now that every seed token is in both.)*

---

## 7. Owed Andy's hands

- ✅ **Migration `0005` APPLIED on Neon (Andy 2026-06-14)** — 4 rows landed. The first apply committed the *wrong* `Bench press rack`/`Climbing Wall`/`Crash pad` tokens; **corrected in place** with two `UPDATE`s (hotel `equipment_tags` → `Bench`; climbing → `{Treadwall, Hangboard, Pull-up bar, Campus board}`). Re-run of the missing-tag check returns 0 rows = clean.
- ⛔ **BLOCKING (pre-merge) was: apply 0005 before deploy** (the `etl_version_set` digest queries the table every plan-gen → deploy-ahead crashes plan-gen, apply-first like 0004). **Now satisfied** — safe to merge #603 once the two UPDATEs are confirmed.
- (carried, unrelated) the post-#572 live **T3 *refresh*** re-verify (diag token + Andy pasting logs, Rule #14).

---

## 8. Next session

- **Slice 4 — away craft** (the literal WS-H [#581](https://github.com/ahorn885/exercise/issues/581) (b)+(c)): craft↔locale ∪ craft↔window → populates the away env's `owned_crafts`, today hard-coded `[]` (F4) at `orchestrator.py` away branch. Needs DDL (`athlete_craft_locale` + a window craft carrier) — design-first, Trigger #3.
- **Slice 5 — capture UX polish** (nav-link to `/profile/event-windows`; plan-gen review panel; the 2b round-trip form-state preservation).
- (split out) #592 race-location terrain/weather; #593 reduced-volume travel days.

### 8.1 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — top entry = this session.
3. `CARRY_FORWARD.md` — WS-H Event Windows top block.
4. This handoff.
5. `designs/Event_Windows_Design_v1.md` §F8 (+ §6 slicing).
6. `./scripts/verify-handoff.sh` (from `aidstation-sources/`).

---

## 9. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Baseline table + seed | `etl/migrations/layer0/0005_seed_location_category_baseline.sql` | `CREATE TABLE … location_category_equipment_baseline`; 4 seed rows; terrain FK + row-count `RAISE EXCEPTION`, equipment FK `RAISE NOTICE` |
| Slug→baseline map + loader | `locations.py` | `_CATEGORY_BASELINE_KEY` (7 slugs→4); `load_category_baselines`; `locale_assumed_baseline_display` |
| Substitution | `locations.py` | `if baselines and not out[locale]:` in `cluster_equipment_by_locale`; `if baselines and not coerced:` in `cluster_terrain_by_locale` |
| Cache family | `layer4/orchestrator.py` | `"location_category_equipment_baseline": "0C"` in `_LAYER0_TABLE_FAMILY`; away-branch `assumed_baseline = locations.locale_assumed_baseline_display(...)` |
| Segment field | `layer4/session_feasibility.py` | `EventWindowSegment.assumed_baseline_category: str \| None = None` |
| Overlay note | `layer4/per_phase.py` | `_event_window_label` appends "assumed from the standard … baseline — log … on arrival" |
| Tests | `tests/test_layer4_location_baselines.py` | 19 cases + overlay-note (`test_layer4_event_windows.py`) + family-map (`test_layer4_orchestrator.py`) |
| Suite | — | 2452 passed / 30 skipped |
| Owed-hands | — | migration 0005 applied on Neon BEFORE merge (blocking) |
