# Event Windows — Slice 1: subtractive home windows — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (forks ratified 2026-06-14). **This is the Slice-1 build spec** — the smallest end-to-end vertical: `indoor_only` + `locale_unavailable` home windows, consumed by plan-gen.
**Status:** SPEC — **BUILD-READY.** §4 seam ratified Option A (Andy 2026-06-14, with the cascade-resolves-the-tier correction). Remaining: Trigger-#1 prompt wording (at build) + DDL apply on Neon (owed Andy's hands).
**Date:** 2026-06-14

---

## 1. Purpose + scope

Let the athlete declare date-bounded **subtractive home windows** and have plan-gen resolve the affected days against the reduced home environment:
- **`indoor_only`** — home cluster minus all outdoor terrain (weather / childcare).
- **`locale_unavailable(L)`** — home cluster minus one specific locale (gym remodel, park flooded).

**In scope:** the `athlete_event_windows` table (these two override types), per-week environment overlay in the cascade, the deterministic placement-feasibility rule (§4), per-week feasibility feed + prompt directive, cache hash, minimal capture/review.
**Out of scope (later slices):** `away` windows + destination locale (Slice 2), category equipment baselines (Slice 3), away craft (Slice 4), full capture UX (Slice 5), `reduced_volume` (#593), race inference (#592).

**Success criteria:** (a) no windows → byte-identical plans (regression); (b) a 2-day `indoor_only` window → those days' outdoor cardio composes indoor/strength, the rest of the week unchanged, weekly counts conserved unless a count genuinely can't fit the unconstrained days; (c) a `locale_unavailable` on the only climbing gym → climbing routes to another cluster locale or substitutes; (d) adding/moving a window invalidates only overlapping synthesis.

---

## 2. Boundaries

- Home cluster only — no new locations, no craft, no baselines, no away environment.
- **Counts stay deterministic.** The window changes *which days are usable* and *per-day feasibility*; it does not by itself change a discipline's weekly session count except via the deterministic overflow rule (§4). The E2 saturation cap is unchanged.
- The LLM's job is unchanged in kind: it still **places** sessions on days and composes content; it gains a hard constraint ("these dates are env X") and never decides feasibility or counts.

---

## 3. Data model (DDL — owed Andy's hands, Neon egress blocked)

`athlete_event_windows` (idempotent `_PG_MIGRATIONS` CREATE):

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `user_id` | INT NOT NULL | athlete-scoped (F1) |
| `start_date` | DATE NOT NULL | inclusive |
| `end_date` | DATE NOT NULL | inclusive; single-day = start==end |
| `override_type` | TEXT NOT NULL | `indoor_only` \| `locale_unavailable` (Slice 2 adds `away`) |
| `unavailable_locale` | TEXT NULL | the `locale_profiles.locale` slug when `override_type='locale_unavailable'` |
| `notes` | TEXT DEFAULT '' | |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

Constraints kept in app code (mirrors the project's no-CHECK convention): `end_date >= start_date`; `unavailable_locale` required+resolvable iff `locale_unavailable`. New `athlete_event_windows_repo.py` (`load_event_windows(db, user_id)`, `replace/add/delete`, + Layer-1/plan-cache eviction mirroring `athlete_crafts_repo.evict_layer1_on_crafts_change`).

---

## 4. THE grid↔synthesis seam (Trigger #5 — ratification gate)

**The problem.** The deterministic grid emits **weekly per-discipline counts** (`session_grid.DisciplineAllocation.sessions_this_week`); the LLM **places** them on days (`per_phase` synthesis). A window covers *part* of a week (each grid week → a date range via `per_phase.py:1647-1654` `phase_spec.start_date + (week-1)*7`). So within one week a discipline can be feasible on some days and not others. How do per-day constraints meet weekly counts?

**Shared mechanics (both options).** Per (phase, week): compute the week's date range (`per_phase.py:1647-1654`), find overlapping windows, and resolve `_build_terrain_feasibility` **per distinct environment present that week** — the default home cluster AND the reduced environment (home minus outdoor terrain for `indoor_only`, or minus locale L for `locale_unavailable`). **No new resolver — just a smaller locale/terrain input** (design §5). Each day then has an active environment, hence a per-(day, discipline) cascade tier. `good_days(D)` = the days whose active environment gives D its **primary** (default-home) tier; the rest are the window days where D takes its **reduced-environment** tier (which the cascade may still resolve to a valid outdoor terrain).

### Option A — deterministic overflow retiering (RATIFIED, Andy 2026-06-14)
**Key correction (Andy): the overflow tier is NOT a fixed indoor/strength downgrade — it's whatever the per-environment cascade resolves.** These are *events*, so the changed environment gets its own full `resolve_craft_terrain_feasibility` pass and may land on a **different-but-valid outdoor terrain** (a hotel-neighborhood run, scree-running in the Alps), **another cluster locale** (`locale_unavailable` where the discipline still has terrain elsewhere in the cluster), **indoor**, *or* **strength** — whatever that environment yields. The seam never assumes a downgrade.

So, per (week, discipline), let **`good_days(D)`** = the days in the week whose active environment resolves D to its **primary desired tier** (the home/default resolution), and let the **reduced tier** = D's cascade tier under the window's environment (which itself may still be a fine outdoor tier):
- if `D.sessions_this_week ≤ |good_days(D)|` → **all sessions at the primary tier**; emit a placement directive ("place D's sessions on `<good_days>`"). The LLM just avoids the windowed days. **No retier** (the common 1-2-day-slack case).
- else → the overflow `(sessions_this_week − |good_days(D)|)` sessions are **deterministically retiered to D's reduced-environment cascade tier** (different terrain / another locale / indoor / strength — per the cascade, not assumed), placed on the windowed days; the remainder stay primary on the good days.

For Slice 1's home subtractions the reduced tier usually resolves to: `indoor_only` → indoor/strength (no outdoor terrain remains); `locale_unavailable` → often **unchanged** (the discipline still has terrain at another cluster locale → no retier at all), else indoor/strength. The away outdoor cases (hotel run, Alps scree) ride the **same** mechanism in Slice 2 — the cascade simply resolves the destination's real terrain.

*Deterministic for count + tier; the LLM only places within the named days (its existing job).* Fits the arc's "deterministic defensive routes; reserve the LLM for content" principle (Andy 2026-06-13). The only new code is the per-(week,discipline) good-days arithmetic + the directive; the tier itself reuses the existing cascade.

### Option B — LLM placement-feasibility
Feed the date→environment map + per-environment tiers; instruct the LLM to place feasible-where-feasible and substitute when it can't fit. Less new deterministic code, but pushes the *which-substitutes* decision to the LLM — the exact probabilistic-defensive-route shape the saturation arc was built to remove. **Not recommended.**

**Recommendation: Option A.** It keeps which/how-many deterministic, degrades to "just avoid these days" in the common case, and only substitutes on genuine overflow. **→ Andy: ratify A (or B) before build.** Open sub-detail under A: when overflow forces substitution, which sessions (lowest-priority-first, reusing the E2 trim order) — proposed yes.

---

## 5. Change surface (≤5 substantive files)

1. **`athlete_event_windows_repo.py`** (new) — reads/writes + eviction.
2. **`layer4/orchestrator.py`** — load windows overlapping the plan span; build the per-(week,environment) feasibility set; the §4-A constrained-days/overflow arithmetic; per-environment `_build_terrain_feasibility` calls with reduced inputs. Rule #15 log.
3. **`layer4/per_phase.py`** — feed per-week feasibility + the date→environment map + placement directive into the `=== Session feasibility ===` block (Trigger #1 wording at build).
4. **`layer4/hashing.py`** — `compute_event_windows_hash` into `plan_create_key` + `plan_refresh_key`.
5. **Capture UI** — minimal: an event-window list + add/delete on the profile + the plan-gen review panel hook (reuse existing locale picker for `locale_unavailable`). May split to a 6th file (template) — flag at build if it pushes the ceiling; the route + template are thin.
6. **Tests** (not counted) — `tests/test_layer4_event_windows.py` + an orchestrator wiring test.

The DDL migration rides in `init_db.py` (bookkeeping-adjacent; the substantive logic is the 5 above).

---

## 6. Caching

`compute_event_windows_hash` = a stable digest of the windows overlapping `[plan_start, plan_end]` (type + dates + `unavailable_locale`), folded into both plan keys (mirrors `compute_terrain_feasibility_hash`, #556). No-windows → empty digest → byte-identical key (success criterion (a)). A window edit invalidates exactly the overlapping synthesis; the **arrival-regen loop** (design F6) falls out of this once Slice 2/3 land.

---

## 7. Rule #15 logging

Per (phase, week) with an active window, print the inputs + decision: `event_window_overlay: <phase>:w<W> dates=<range> override=<indoor_only|locale_unavailable:L> good_days={D-008:5,...} retiered={D-008:[1→indoor],...}` — naming, per retiered session, the **tier the cascade landed on** (not assuming indoor/strength). So a surprising windowed-day plan is diagnosable from logs alone (Rule #15).

---

## 8. Edge cases
- Window fully covers a week → `unconstrained_days=0` → all of that week's outdoor-cardio retiers (Option A overflow with 0 capacity).
- Window outside the plan span → ignored (hash unaffected).
- `locale_unavailable` on a locale not in the cluster → no-op (log it; the locale was never feeding feasibility).
- Overlapping windows on the same dates → union of subtractions (both applied).
- `indoor_only` + the cluster has an indoor machine → outdoor cardio retiers to INDOOR before STRENGTH (existing cascade order holds under the reduced terrain).

---

## 9. Test scenarios
1. No windows → identical grid + feasibility + cache key. *Regression.*
2. `indoor_only` 2 days, discipline has slack → count kept, directive names the good days, no substitution.
3. `indoor_only` covering enough days that an outdoor count can't fit the good days → deterministic overflow retiers the excess to its reduced-env tier (indoor/strength, since no outdoor remains); count conserved across disciplines.
4. `locale_unavailable` on a park where **another cluster locale has the same terrain** → trail run stays `exact` at the fallback locale (**no retier** — the "not always a downgrade" case); the gym is unaffected.
5. `locale_unavailable` on the **only** locale with a terrain → that discipline's window-day sessions retier to whatever the cascade then resolves (indoor/strength); other disciplines unaffected.
6. Cache: add/move/delete a window → only overlapping weeks’ synthesis recomputes.
7. Rule #15 line present + correct on a windowed week.

---

## 10. Open items / sign-off
- **§4 seam — RATIFIED Option A** (Andy 2026-06-14), with the correction that the retier tier is the per-environment **cascade** result (may be valid outdoor / another locale / indoor / strength), never an assumed downgrade. **Spec is build-ready.**
- Trigger-#1 feasibility-block + placement-directive wording — at build (the only remaining sign-off).
- DDL apply on Neon — owed Andy's hands.

## 11. Gut check
- **The seam is the whole risk; everything else is mechanical.** Option A localizes the new determinism to a small per-week arithmetic and keeps the LLM in its existing placement lane — lowest-surprise path. If A's overflow rule feels too clever, the fallback isn't B (probabilistic) but "fail the week to the existing E2/strength path" — uglier but still deterministic.
- **Counts-conserved claim depends on the overflow retier** composing the session at its reduced-env cascade tier *in place* (different terrain / locale / indoor / strength), so volume is preserved, not dropped — consistent with E2's "never drop training time."
- **What might bite:** a week split across many tiny windows (Slice 2's 3-4-locations case) makes `unconstrained_days` per-discipline bookkeeping fiddlier — but Slice 1 is home-only (at most indoor_only + a locale drop), so the arithmetic stays simple here; the multi-window stress lands in Slice 2 by design.
