# Event Windows (home-constraint + away-location) + Away Craft — Design v1

**Workstream:** WS-H (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H) on `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§6a). **Supersedes the working title "Away-Training-Windows"** — Andy reframed it to **event windows** (they constrain training at home too, not only away).
**Status:** DESIGN-FIRST — Trigger #3 (new DDL) + #5 (architecture) + #2 (the category-baseline reference data, F8). **Forks F1/F2/F4 ratified; F3 revised to per-day; F8/F9/F-race added from Andy's 2026-06-14 feedback.** No build until the re-sliced Slice 1 (§6) is spec'd + signed off.
**Date:** 2026-06-14

---

## 1. The problem (reframed)

WS-H wanted craft-availability for *away* locations. Investigating it surfaced that v2 plan-gen has **no date-windowed environment surface at all** — the feasibility cascade resolves one home cluster for the whole plan (`orchestrator._build_terrain_feasibility`, `cluster = locations.cluster_locale_ids`, `orchestrator.py:371`). Away craft is just one axis of that missing surface.

**Andy's reframe (2026-06-14) widens it further:** the thing we're missing isn't "travel" — it's **event windows**: date-bounded periods where the athlete's training environment differs from their default. Three override types:
- **`indoor_only`** — the athlete is *home* but can't train outdoors: weather, or (Andy's case) kids over who need supervision. (v1 had exactly this via `plan_travel.indoor_only`.)
- **`locale_unavailable`** — *home cluster, but one place in it is out* (Andy): the gym is closed for remodeling, or the nearby park is flooded — suppress that one locale for the window.
- **`away`** — the athlete is at a *different location* (work trip, training camp), with that location's terrain/equipment/craft.

The v1 app **had** this (date-based, on `/coaching/review`, writing `plan_travel` with an `indoor_only` flag) and it was **left behind** in v2 — and its location model was the now-retired `home/hotel/partner/airport` enum (WS-B/#589). So this isn't a re-port; it's the v2 rebuild of a real, lost feature.

---

## 2. Current state (grounded)

| Concern | Today | Anchor |
|---|---|---|
| Feasibility resolution | One pass over the home cluster, **whole plan**, no date variation | `orchestrator.py:361-451` |
| Cascade purity | Pure over a `locale_order` + per-locale terrain/equipment maps | `session_feasibility.resolve_craft_terrain_feasibility` |
| `owned_crafts` | One flat athlete-wide list, all disciplines/locales | `orchestrator._collect_athlete_crafts` (`orchestrator.py:196`) |
| Locale model | `locale_profiles(user_id, locale)` + `lat/lng`, `preferred`, `locale_terrain_ids[]`, `gym_profile_id`; per-athlete equipment overrides; `mapbox_id` | `init_db.py:225, 1129, 1251, 1501` |
| Session date | Each session lands on a specific day; grid produces **weekly counts**, synthesis **places** them on days | `per_phase.py` grid + synthesis |
| Travel in v2 | NONE. v1 `plan_travel` (incl. `indoor_only`) is dead to v2 | `routes/coaching.py:62-70` |
| Equipment baselines by category | NONE — equipment is per-locale actuals only | — |

**The lucky break holds:** the cascade is pure over a locale/environment set, so window-awareness = "resolve once per distinct environment, map each session **date** to its environment." The new cost is granularity (per-day, §4 F3) and the grid↔synthesis seam (§5).

---

## 3. Target model — event windows

An **event window** = `{date range [start, end], an environment override}`. The override is one of three types — the first two are *subtractions from the home cluster*, the third *replaces* it:
- **`indoor_only`** → suppress **all outdoor terrain** from the home cluster for those dates (home but can't train outdoors — weather, or kids needing supervision). Outdoor cardio → indoor/strength.
- **`locale_unavailable(L)`** → suppress **one specific cluster locale** L (its terrain + equipment) for those dates — *"this cluster, but not this place in it."* Andy's examples: the gym is closed for remodeling, or the nearby state park is closed for flooding. Sessions needing L route to another cluster locale or substitute.
- **`away(dest)`** → **replace** the home cluster with a destination location (a `locale_profiles` row, reused or created inline) + optional brought-craft + assumed-vs-logged equipment.

The first two share one resolver path — *resolve the home cluster minus something* — so Slice 1 covers both. `away` is *a different cluster* (Slice 2).

Windows are **athlete-level** (a standing calendar), **sub-week** (a single window is often 1-3 days; a week may contain several), reviewed/edited/appended **at plan generation**. Plan-gen maps each session's **date** to the active window (if any) and resolves that day against the window's environment; non-windowed dates resolve against the home cluster (today's behavior).

---

## 4. Design forks

### F1 — Window scope + capture point — **RATIFIED: athlete-level + plan-gen review/edit/append panel**
A standing `athlete_event_windows` calendar, surfaced for **review / edit / append at plan generation** (restores the v1 `/coaching/review` UX). The panel must allow **adding a new location inline** (Andy: the event's location may not exist yet) — pick an existing locale OR create one on the spot, reusing the locale builder.

### F2 — Away destination — **RATIFIED: reused `locale_profiles` row (+ inline create)**
Destination = a `locale_profiles` row (reuses the entire terrain/equipment/override + cascade-reader stack; gives craft↔location for free). Andy's strategic frame: *"travel is how we build our crowd-sourced locations database"* (differentiator #8). Inline-create from the window panel (F1). Dedup by the existing `locale_profiles.mapbox_id` / `gym_profiles.mapbox_id UNIQUE` so two athletes' "Belfast hotel" can converge into shared crowd data — note for the Slice-2 spec.

### F3 — Granularity — **REVISED (Andy): per-DAY, sub-week (was per-week)**
My v0 assumed week-granularity; **wrong.** Andy: *"I may be in 3-4 different locations in a week due to work travel."* So:
- Each event window is **date-ranged** (can be a single day).
- Each **session** maps to its **date's** active window (else home). The environment is resolved **per distinct environment present in the plan span**, and each session is composed against its date's environment.
- **The grid↔synthesis seam (load-bearing):** the deterministic session grid produces **weekly per-discipline counts**; the synthesizer **places** them on days. With per-day feasibility, a discipline can be feasible some days of a week and not others. Resolution direction (for the Slice-1 spec): keep the **count** allocation weekly, but compute feasibility **per (week × environment present that week)** and have synthesis **place the feasible-where-feasible** — i.e. an outdoor-cardio session in a week that's partly indoor-only-at-home gets placed on a non-constrained day if one exists, else substituted (indoor/strength) for that week. The deterministic resolver decides *which/how-many*; the LLM only places within the allowed days. **This is the core new machinery and the main Slice-1 design risk.**

### F4 — Away craft default — **RATIFIED: none unless declared**
Home cluster → all owned craft (WS-G). Away locale → none unless declared via craft↔locale or craft↔window (the brought-craft set on the window). Empty-away degrades through the cascade (terrain → indoor → strength → reallocate).

### F5 — Capture UI
The event-window panel (profile + the plan-gen review panel, F1): date range, kind, location (pick/create, F2), home-constraint flags (F9), brought-craft (F4), equipment-baseline-vs-logged (F8). Reuses the locale builder for the inline-create path.

### F6 — Caching + refresh + **the log-on-arrival → regen loop (Andy)**
- A `compute_event_windows_hash` (windows overlapping the plan span + their locations/constraints/craft) folds into `plan_create_key` **and** `plan_refresh_key` (mirrors `compute_terrain_feasibility_hash`, #556).
- **The arrival loop (Andy's Belfast example):** the plan is first built on the **assumed** category baseline (F8) for a not-yet-seen hotel gym. When the athlete arrives and **logs the hotel's actual equipment** (updating that away locale's profile) — and any craft they brought — the locale/window hash changes → a **T1/T2 refresh** re-plans the affected window with the real equipment. This falls out of the existing locale-edit + refresh machinery once the window feeds the cache key; the only new piece is the assumed→logged transition (F8).

### F7 — Synthesis prompt (Trigger #1)
The `=== Session feasibility ===` block gains per-window directives: *"Days X–Y: <home, indoor-only | away at <place>> — available terrain/equipment/craft: …; compose these days against THAT environment."* Wording deferred to build (Trigger-#1 sign-off then).

### F8 — Category equipment baselines (NEW, Andy) — **Trigger #2**
*"I'm at a hotel in Belfast, I don't know what its gym has, so we have a baseline for hotels that we ASSUME and build the plan around, but the athlete can update the hotel's profile when they arrive and regen."*
- A new away locale whose **category** has a known equipment shape inherits a **default assumed equipment profile** until the athlete logs actuals.
- **These are the *current* locale categories — NOT the retired `home/hotel/partner/airport` enum** (Andy's correction). The category vocabulary already lives in `routes/locales.py:205` `MANUAL_CATEGORIES` (`commercial_chain_gym`, `independent_gym`, `hotel_gym`, `climbing_gym_chain/indie`, `pool_*`, `home_gym`, `outdoor_park`, …). F8 attaches an *assumed equipment set* to a small subset of them.
- **Scope (Andy): just the categories worth assuming —** **commercial gyms** (`commercial_chain_gym` + `independent_gym`), **hotel gyms** (`hotel_gym`), and **maybe climbing gyms** (`climbing_gym_*`). Not residences (athlete-specific), not outdoor parks (terrain, not equipment).
- **Trigger #2:** the baseline *contents* (which equipment each of those ~3 categories assumes) are reference data needing Andy's ratification — a small seed table (e.g. `location_category_equipment_baseline(category, equipment_tags[])`). **Do not author the lists without sign-off.**
- Crowd-sourcing tie-in: assumed baseline → athlete-logged actual → shared `gym_profiles` (F2 dedup, `_resolve_private` keeps residences out). The baseline is the cold-start; the crowd is the warm-start.

### F9 — Subtractive home windows (NEW, Andy) — the simplest vertical
Two override types that **subtract from the home cluster** for a date range (no location change), sharing one resolver path → together they're **Slice 1**:
- **`indoor_only`** — suppress all outdoor terrain (weather / childcare).
- **`locale_unavailable(L)`** — suppress one specific cluster locale (gym remodel, park flooded). The window names which locale.

Both resolve the home cluster *minus something*, then outdoor/locale-bound sessions route to a remaining cluster locale or substitute (indoor/strength). Smallest end-to-end slice (no new location, no craft) yet it exercises the full date-range + per-day machinery.

**Flag set — collapsed (Andy):** I had split `indoor_only` vs `no_outdoor_cardio`; **Andy is right that they're the same** — for feasibility both just suppress outdoor terrain, so there's **one flag: `indoor_only`.** `reduced_volume` (in-transit travel days where the athlete trains less) is **out of scope — deferred to its own GitHub issue** (the athlete handles volume themselves for now). So Slice 1's constraint surface is exactly: `indoor_only` (boolean) + `locale_unavailable` (a cluster-locale reference). No open flag-set question remains.

### F-race — Race locations are real but DIFFERENT — **separate issue (Andy)**
Andy: standardized races (Boston) have meaningful stable locations; AR races change year-to-year. Either way, if the athlete enters a race location we could **LLM-infer the general area's terrain + weather** to (a) *suggest in the UI* "this race likely has <terrain>, train for it" and (b) feed plan-gen. **But race locations should be treated differently from training locations** (a race isn't a place you train *at* during the window; it's the target). The current state confirms the split: `race_events` already models its location **Mapbox-anchored** (`event_locale_*` + `race_terrain`), not as a `locale_profiles` row (`init_db.py:1414-1417`; the `event_locale_id` FK is legacy/nullable). **Decision: out of scope here — file as its own issue** ("race-location terrain/weather inference + UI suggestion + plan-gen feed"). Not folded into event windows.

---

## 5. Cascade + synthesis change

1. **Build the environment set** for the plan span: home cluster (default) + each distinct event-window environment — `indoor_only` (home cluster minus outdoor terrain), `locale_unavailable` (home cluster minus locale L's terrain+equipment), or `away` (the destination's cluster).
2. **Resolve `_build_terrain_feasibility` per environment** — it already takes a locale set + per-locale terrain/equipment maps, so the two subtractive variants are just *the home maps with a subset removed* (no new resolver); add the per-environment `owned_crafts` (F4).
3. **Map each plan week to the environment(s) present** (a week may span several windows, F3), and feed synthesis a **per-(week, environment)** feasibility picture + the date ranges, so it places feasible-where-feasible (§4 F3 seam).

The cascade itself is reused, not rewritten; the new code is the segmentation + per-environment loop + the home-constraint suppression + the per-day placement contract in synthesis.

---

## 6. Re-sliced plan (Andy: "create new slices… so we don't stretch too thin")

- **Slice 1 — subtractive home windows (F9):** `athlete_event_windows` (date range + `indoor_only` bool + `locale_unavailable` cluster-locale ref) + per-environment resolution that resolves *home cluster minus outdoor terrain* (indoor_only) or *minus locale L* (locale_unavailable) + per-(week,env) feasibility feed + cache hash + a minimal capture/review panel. **Smallest end-to-end vertical; no new location/craft/baseline.** Proves the date-range + per-day machinery on Andy's kids/weather + gym-closure cases. DDL: `athlete_event_windows`.
- **Slice 2 — away windows + destination locale (F2) + inline create (F1/F5):** `kind='away'` with a `locale_profiles` destination (pick/create), per-environment cascade against its terrain/equipment, `mapbox_id` dedup. DDL: window→locale link (+ away discriminator on the locale).
- **Slice 3 — category equipment baselines (F8, Trigger #2):** the `hotel/airport/partner` assumed-equipment reference table + the assumed→logged transition + the arrival-regen loop (F6). Needs the baseline-contents sign-off.
- **Slice 4 — away craft (the literal WS-H (b)+(c), F4):** craft↔locale ∪ craft↔window → away `owned_crafts`. DDL: `athlete_craft_locale` + window craft carrier.
- **Slice 5 — capture UX polish (F5):** full panel on profile + onboarding, beyond the minimal Slices 1-2 capture.
- **Separate issue (F-race):** race-location terrain/weather inference.

Each slice ≤5 substantive files, each delivers value, each is independently shippable. Slices 3/4 carry the Trigger-#2/#3 sign-offs.

---

## 7. DDL (owed Andy's hands — Neon egress blocked)
- `athlete_event_windows(id, user_id, start_date, end_date, override_type, indoor_only, unavailable_locale|null, away_locale|null, notes, created_at)` — `override_type ∈ {indoor_only, locale_unavailable, away}`; Slice 1 ships the first two (`away_locale` added in Slice 2).
- away discriminator on `locale_profiles` (e.g. `source`/`kind`) — Slice 2.
- `location_category_equipment_baseline(category, equipment_tags[])` for ~3 categories (commercial/hotel/climbing gym) — Slice 3 (Trigger #2).
- `athlete_craft_locale(user_id, craft_slug, locale)` + window craft carrier — Slice 4.

All via the idempotent `_PG_MIGRATIONS` ALTER/CREATE pattern; applied on Neon by Andy.

---

## 8. Test scenarios (design-level)
1. No windows → byte-identical to today. *Regression guard.*
2. (Slice 1) A 2-day `indoor_only` home window mid-week → those days' outdoor cardio → indoor/strength; rest of week unchanged; weekly counts conserved.
3. (Slice 1) Outdoor-cardio week with a 1-day `indoor_only` window → synthesis places the outdoor session on a non-constrained day (no substitution needed).
3b. (Slice 1) `locale_unavailable` on the only climbing-equipped cluster gym (remodel) → climbing/strength needing it routes to another cluster locale or substitutes; the park (still open) is unaffected.
4. (Slice 2) 3 locations in one week (Andy's work-travel case) → each day resolves against its window's environment; the week carries 3 feasibility pictures.
5. (Slice 3) Away hotel with no logged equipment → plan built on the hotel **baseline**; after logging actuals, a refresh re-plans only that window.
6. (Slice 4) Packraft ticked onto an away window → D-009 `exact` for those days only.
7. Cache: adding/moving a window invalidates only overlapping synthesis.

---

## 9. Open items / sign-off
**Ratified (2026-06-14):** F1, F2, F4; reframe to event windows; F3 per-day; F8 (categories = commercial/hotel/climbing gym, not the retired enum); F9 (the `indoor_only`/`no_outdoor_cardio` split collapsed to one flag; `locale_unavailable` added; `reduced_volume` deferred to its own issue); F-race split out (#592).
**Owed before Slice-1 build:** (1) the **F3 grid↔synthesis seam contract** (weekly counts + per-day placement — the main remaining risk; spec it precisely in Slice 1); (2) Trigger-#1 feasibility-block wording (build time). The flag-set question is **resolved** (`indoor_only` + `locale_unavailable`). **Per-slice triggers:** Slice 3 = Trigger #2 (baseline contents); Slices 1-4 DDL = owed Andy's hands.

## 10. Gut check
- **Slicing is now the safeguard.** The reframe (event windows + per-day + baselines + inline-create + race) is a *lot*; the 5-slice split keeps each shippable and within the file ceiling, per Andy's explicit ask. Slice 1 (home-constraint) is deliberately the smallest vertical so the risky machinery (per-day feasibility) lands behind the least surface.
- **Biggest risk: F3 grid↔synthesis seam.** Weekly counts vs per-day feasibility is a genuine new contract; if it's hairy, Slice 1's `indoor_only` case is the cheapest place to get it right (one environment, no location).
- **Trigger #2 watch (F8):** don't author the commercial/hotel/climbing-gym baselines without sign-off — that's the no-padding rule.
- **Race split is correct** — a race location is a target, not a training environment; conflating them would muddy both. Separate issue (#592) keeps the LLM-terrain-inference idea alive without bloating this arc.
- **Deferred deliberately:** in-transit `reduced_volume` travel days → its own issue (athlete self-manages volume for now, Andy). Keeps Slice 1's constraint surface to exactly `indoor_only` + `locale_unavailable`.
