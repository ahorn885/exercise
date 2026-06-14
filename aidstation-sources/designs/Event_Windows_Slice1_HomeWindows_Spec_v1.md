# Event Windows — Slice 1: subtractive home windows — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (forks ratified 2026-06-14). **This is the Slice-1 build spec** — the smallest end-to-end vertical: `indoor_only` + `locale_unavailable` home windows, consumed by plan-gen.
**Status:** **BUILT + MERGED 2026-06-14** (PR [#596](https://github.com/ahorn885/exercise/pull/596) squash-merged to `main`; branch `claude/compassionate-keller-ej5tcx`; handoff `handoffs/V5_Implementation_WSH_EventWindows_Slice1_Build_2026_06_14_Closing_Handoff_v1.md`). §4 model held as built (existing cascade per date-segment). Trigger-#1 overlay wording **signed off by Andy 2026-06-14**. **DDL APPLIED on Neon 2026-06-14 (verified — 8 columns) → Slice 1 fully live in prod.** **Deferred (flagged):** refresh-overlay render is create-first (the hash param is on `plan_refresh_key`; the refresh caller doesn't feed it yet).
**Date:** 2026-06-14

---

## 1. Purpose + scope

Let the athlete declare date-bounded **subtractive home windows** and have plan-gen resolve the affected days against the reduced home environment:
- **`indoor_only`** — home cluster minus all outdoor terrain (weather / childcare).
- **`locale_unavailable(L)`** — home cluster minus one specific locale (gym remodel, park flooded).

**In scope:** the `athlete_event_windows` table (these two override types), date-segmented resolution of the **existing** cascade against each reduced environment (§4), date-scoped synthesis feasibility feed + soft placement directive, cache hash, minimal capture/review.
**Out of scope (later slices):** `away` windows + destination locale (Slice 2), category equipment baselines (Slice 3), away craft (Slice 4), full capture UX (Slice 5), `reduced_volume` (#593), race inference (#592).

**Success criteria:** (a) no windows → byte-identical plans (regression); (b) a 2-day `indoor_only` window → those days resolve to the reduced-env tier (outdoor cardio composes indoor/strength), the rest of the week unchanged, weekly counts unchanged; (c) a `locale_unavailable` on the only climbing gym → climbing routes to another cluster locale or substitutes (cascade decides); (d) adding/moving a window invalidates only overlapping synthesis.

---

## 2. Boundaries

- Home cluster only — no new locations, no craft, no baselines, no away environment.
- **Counts unchanged.** In Slice 1 the grid + E2 resolve against the default home environment; the window only re-scopes the *per-date* feasibility synthesis composes against. The E2 saturation cap is unchanged.
- The LLM's job is unchanged in kind: it still **places** sessions on days and composes content per each date's deterministic cascade tier; it never decides feasibility or counts.

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

## 4. Resolution model — it's the existing cascade, date-segmented (Andy 2026-06-14)

**Andy's correction (adopted): this is no different from normal plan-gen — it's the same deterministic proxy/substitution cascade, just resolving against different terrain/equipment sets.** My earlier draft invented a per-week "good-days / overflow-retiering" arithmetic; that was over-engineered and is **removed**. The cascade (`resolve_craft_terrain_feasibility` → exact→proxy→indoor→strength→reallocate) already does every substitution decision deterministically. A window changes nothing about *how* it resolves — only the `(terrain, equipment)` inputs for a date range.

The **only genuinely new element is the time dimension.** Today the cascade emits one plan-wide `dict[discipline → TerrainResolution]`; with windows it emits one **per date-segment**:

1. **Segment the plan span by date** into environments: the default home cluster, plus each window's reduced environment (`indoor_only` = home cluster minus outdoor terrain; `locale_unavailable(L)` = home cluster minus locale L's terrain+equipment).
2. **Run the existing cascade once per environment** — same function, smaller terrain/equipment input — giving `feasibility_by_segment[date_range] → dict[discipline → tier]`. No new resolution logic.
3. **Counts stay on the default (home) environment.** The grid + E2 saturation cap are **unchanged** in Slice 1: a discipline's weekly *count* is computed against home, exactly as today. (Short sub-week home windows don't shift weekly volume; whole-week/multi-week count shifts are an `away`-window concern — Slice 2 — and even there it's the grid consuming the segment's cascade tiers, still no bespoke arithmetic.)
4. **Synthesis composes per date.** `per_phase` renders the same `=== Session feasibility ===` block, now **date-scoped** (the active environment + its tiers per date range), plus a **soft directive**: *"prefer placing outdoor-dependent disciplines on the unconstrained days."* The LLM places (its existing job) and composes each session against its date's tier — reusing proxy/substitution identically. A session that lands on a window day naturally composes at that day's tier (e.g. indoor/strength under `indoor_only`); volume is conserved either way.

**Why no overflow arithmetic is needed.** The per-date tier is fully deterministic (the cascade decides it); the LLM only chooses *which day*, which it already does for every session. So nothing probabilistic is added — there's no LLM "feasibility decision," just placement bounded by deterministic per-day tiers. When a discipline's count exceeds the unconstrained days, the surplus simply composes at the window tier through normal placement; pre-computing *which* session that is buys nothing.

**The one accepted limitation (Slice 1):** because counts resolve against home, E2 won't *pre-cap* strength induced by a window day's substitution — a constrained week could carry +1–2 strength beyond the usual cap at composition time. For short home windows that's acceptable (the athlete is genuinely constrained those days) and `_rule_strength_frequency_band` is advisory-only. If it ever bites, the fix is to feed the grid/E2 the segment tiers for weeks a window fully covers — deferred to when `away` (Slice 2) needs it.

---

## 5. Change surface (≤5 substantive files)

1. **`athlete_event_windows_repo.py`** (new) — reads/writes + eviction.
2. **`layer4/orchestrator.py`** — load windows overlapping the plan span; segment the span by environment; call the **existing** `_build_terrain_feasibility` once per environment with its reduced terrain/equipment input → `feasibility_by_segment`. No new resolution logic. Rule #15 log.
3. **`layer4/per_phase.py`** — render the date-scoped `=== Session feasibility ===` block (per-segment tiers + date ranges) + the soft "prefer outdoor disciplines on unconstrained days" directive (Trigger #1 wording at build).
4. **`layer4/hashing.py`** — `compute_event_windows_hash` into `plan_create_key` + `plan_refresh_key`.
5. **Capture UI** — minimal: an event-window list + add/delete on the profile + the plan-gen review panel hook (reuse existing locale picker for `locale_unavailable`). May split to a 6th file (template) — flag at build if it pushes the ceiling; the route + template are thin.
6. **Tests** (not counted) — `tests/test_layer4_event_windows.py` + an orchestrator wiring test.

The DDL migration rides in `init_db.py` (bookkeeping-adjacent; the substantive logic is the 5 above).

---

## 6. Caching

`compute_event_windows_hash` = a stable digest of the windows overlapping `[plan_start, plan_end]` (type + dates + `unavailable_locale`), folded into both plan keys (mirrors `compute_terrain_feasibility_hash`, #556). No-windows → empty digest → byte-identical key (success criterion (a)). A window edit invalidates exactly the overlapping synthesis; the **arrival-regen loop** (design F6) falls out of this once Slice 2/3 land.

---

## 7. Rule #15 logging

Per date-segment with an active window, print the inputs + decision: `event_window_overlay: <phase>:w<W> dates=<range> override=<indoor_only|locale_unavailable:L> tiers={D-008:indoor, D-001:exact, ...}` — naming, per discipline, the **tier the cascade landed on** for that segment (not assuming indoor/strength). So a surprising windowed-day plan is diagnosable from logs alone (Rule #15).

---

## 8. Edge cases
- Window fully covers a week → every day is the reduced environment → the discipline's whole-week tier is the reduced-env cascade result (e.g. all-indoor); same as today's uniform resolution.
- Window outside the plan span → ignored (hash unaffected).
- `locale_unavailable` on a locale not in the cluster → no-op (log it; the locale was never feeding feasibility).
- Overlapping windows on the same dates → union of subtractions (both applied) before the cascade runs.
- `indoor_only` + the cluster has an indoor machine → the reduced-env cascade lands INDOOR before STRENGTH (existing tier order holds under the smaller terrain).

---

## 9. Test scenarios
1. No windows → identical grid + feasibility + cache key. *Regression.*
2. `indoor_only` 2 days, discipline has slack → count unchanged; the date-scoped block + soft directive lead the LLM to place outdoor sessions on the open days; no substitution.
3. `indoor_only` covering the whole week → that week's outdoor cardio resolves to the reduced-env tier (indoor/strength, no outdoor remains), exactly like a uniform infeasible resolution today.
4. `locale_unavailable` on a park where **another cluster locale has the same terrain** → trail run stays `exact` at the fallback locale (the cascade finds it — "not always a downgrade"); the gym is unaffected.
5. `locale_unavailable` on the **only** locale with a terrain → that discipline's windowed-segment tier is whatever the cascade then resolves (indoor/strength); other disciplines unaffected.
6. Cache: add/move/delete a window → only overlapping weeks’ synthesis recomputes.
7. Rule #15 line present + correct on a windowed segment.

---

## 10. Open items / sign-off
- **§4 model — SETTLED** (Andy 2026-06-14): the existing cascade resolved per date-segment; no bespoke seam arithmetic. **BUILT.**
- **Trigger-#1 wording — SIGNED OFF** (Andy 2026-06-14): the `=== Event-window overlay (deterministic — date-scoped routing) ===` block + the `Placement preference (soft)` directive, rendered by `per_phase._format_event_window_overlay`.
- **DDL apply on Neon — DONE 2026-06-14** (Andy applied + verified the 8-column schema; the idempotent CREATE is in `init_db._PG_MIGRATIONS`).
- **Deferred follow-up:** refresh-overlay render (create-first this slice, mirroring #540→#557). The `event_windows_hash` param is present on `plan_refresh_key`; wiring the refresh caller to supply it + render the overlay in the tier prompts is the next step.

## 11. Gut check
- **The new surface is small** — segment the span, call the existing cascade per segment, render it date-scoped. The substitution intelligence is entirely reused; the only genuinely new code is date-bucketing + the per-segment loop.
- **Volume conservation** is automatic: a windowed-day session still happens, composed at its segment's cascade tier (different terrain / locale / indoor / strength) — never dropped (consistent with E2).
- **What might bite:** the accepted limitation (§4) — counts resolve against home, so a window-induced substitution can push a week +1–2 over the E2 strength cap at composition time. Marginal for short home windows; the fix (feed the grid the segment tiers for fully-covered weeks) waits for `away`/Slice 2, where multi-week windows make it matter.
