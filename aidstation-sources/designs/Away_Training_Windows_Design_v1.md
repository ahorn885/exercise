# Training-Away-From-Home Windows + Away Craft Availability — Design v1

**Workstream:** WS-H (issue [#581](https://github.com/ahorn885/exercise/issues/581) Phase H) on the north-star plan `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (§6a).
**Status:** DESIGN-FIRST — Trigger #3 (new DDL / cross-layer surface) + Trigger #5 (architectural alternatives). **Forks F1/F2/F4 RATIFIED by Andy 2026-06-14 (see §4); race-overlap investigated (§4 F-race). Build after Slice-1 spec + Trigger-#1 prompt sign-off.**
**Date:** 2026-06-14
**Predecessor context:** WS-G shipped (craft = athlete-owned canonical set B, available home-cluster-wide; validated live pv=71). WS-I shipped (unified craft/terrain cascade). This design is the *away* half of the craft model — and it surfaces that "away craft" can't exist without an away **window** surface that v2 plan-gen doesn't have yet.

---

## 1. The problem (the WS-H finding)

WS-H as filed wants two things: **(b)** craft↔location (an owned craft is available at a specific away location) and **(c)** craft↔travel-event (a craft attached to a trip, available at its location for its window) — issue #581: *"a per-locale craft-availability read in the cascade … locale-aware for away locations while staying home-cluster-wide by default."*

**Both halves presuppose a feature that does not exist:** plan-gen has no concept of the athlete training away from home for a date window. The feasibility cascade resolves every discipline against **one** locale set — the home cluster — for the **entire** plan:

- `orchestrator._build_terrain_feasibility` does `cluster = locations.cluster_locale_ids(db, user_id)` = home (`preferred=TRUE`) + locales within 42.2 km, then passes that single `cluster` as `locale_order` to every discipline's cascade (`layer4/orchestrator.py:371, 422, 443`). No per-week / per-window locale variation.
- An **away** location (>42 km — the whole point of (b)) is **excluded from the cluster by definition**, so the cascade never visits it. Associating a craft with it has no consumer.
- There is **no v2 travel/trip model.** `plan_travel` exists but is **v1-legacy** (FKs `training_plans`, read only by `routes/plans.py` / `dashboard.py` / `coaching.py` — the retired monolithic coaching path). The v2 pipeline (`plan_versions`, `layer4/`) never reads it. The only "travel" in `layer4/` is a `travel_day` *session category* (`per_phase.py:591`), unrelated.
- `routes/plan_create.py` takes no travel/away input.

**Conclusion:** away-craft is the *last axis* (alongside terrain + equipment at the destination) of a missing mid-sized feature — **"training-away-from-home windows."** Building the craft↔location / craft↔event store alone would be an **unconsumed surface** — the WS-F failure shape (#578, built craft-from-equipment with no consumer, reverted #580). So this design specs the **whole away-window feature**, with away-craft (the literal WS-H) as one slice inside it.

---

## 2. Current state (grounded)

| Concern | Today | Anchor |
|---|---|---|
| Craft store (set B) | Athlete-scoped, global; flat list, no location dim | `athlete_crafts_repo.py`; `discipline_baseline_{cycling,paddling}` |
| `owned_crafts` assembly | One flat list for ALL disciplines, ALL locales | `orchestrator._collect_athlete_crafts` (`orchestrator.py:196`) |
| Feasibility resolution | One pass over the home cluster, whole plan | `_build_terrain_feasibility` (`orchestrator.py:361-451`) |
| Cascade purity | Pure over `locale_order` + per-locale terrain/equipment maps | `session_feasibility.resolve_craft_terrain_feasibility` |
| Locale model | `locale_profiles(user_id, locale)` + `lat/lng`, `preferred`, `locale_terrain_ids TEXT[]`, `gym_profile_id` FK; per-athlete equipment overrides | `init_db.py:225, 1251, 1501` |
| Cluster | home + radius ≤42.2 km, home-first | `locations.cluster_locale_ids` |
| Plan date span | `plan_start_date` (anchor) + scope window | `orchestrator.py:1088, 1226` |
| Synthesis feasibility feed | One `terrain_feasibility` dict per phase prompt; session grid is per-(phase, week) | `per_phase.py:840, 885` |
| Travel in plan-gen | NONE in v2. **v1 HAD it and it was left behind** — see below | `routes/coaching.py:62-70` |

**The v1 travel surface that was left behind (answers F1's "did we have this?").** The v1 app captured trips on the **`/coaching/review/<plan_id>`** page: the athlete appended `{start_date, end_date, locale, city, indoor_only}` rows to `plan_travel` *at the moment of plan review/regeneration* (`routes/coaching.py:62-70`). That "review/edit/append trips when generating a plan" UX is exactly what Andy wants preserved (F1). **But** its `locale` was the abstract trip-**type** taxonomy `('home','hotel','partner','airport')` (`coaching.py:27`, `TRIP_LOCALE_TYPES`) — the **same legacy enum WS-B (#589) just retired.** So v2 doesn't merely re-port v1 travel; it *completes the WS-B arc* — travel destinations become **real locales** (terrain + equipment, crowd-sourceable, F2) instead of four abstract place-kinds. The v1 `plan_travel` row is plan-scoped and read only by the retired coaching path; it is **superseded**, not reused.

**The one lucky break:** the cascade is already **pure over a locale set**. Making it window-aware is "call it once per distinct environment, then map each plan week to its environment" — not a rewrite of the cascade itself.

---

## 3. Target model — away windows

An **away window** is an athlete-declared fact: *"I'll be training at destination D for date range [start, end]."* Plan-gen resolves sessions whose date falls inside a window against **D's** terrain + equipment + available craft, instead of the home cluster.

Three new pieces:
1. **A window record** — `{date range, destination, available-craft subset}`.
2. **A destination** — somewhere the cascade can read terrain + equipment from.
3. **Window-aware cascade + synthesis** — resolve feasibility per distinct environment; feed each plan **week** the environment active that week.

The forks below (§4) decide the exact shape of 1 and 2; §5 specs 3.

---

## 4. Design forks (Trigger #5 — options + recommendation)

### F1 — Where does a window attach: athlete-level or plan-level?
- **(a) Athlete-level** `athlete_travel_windows(user_id, …)` — a standing "trips calendar." Plan-gen reads windows overlapping the plan's date span.
- **(b) Plan-level** (like v1 `plan_travel`, FK the plan) — re-entered per plan.

**RATIFIED (Andy 2026-06-14): athlete-level, WITH a review/edit/append step at plan generation.** A trip is a real-world fact, not a plan artifact — same reasoning that made craft athlete-owned (WS-G). It survives plan refresh and applies across multiple plans automatically; folds into the cache key by date overlap. **Andy's added requirement:** the plan-gen flow must surface the standing trips for **review / edit / append** before generating — preserving the v1 `/coaching/review` UX (§2) on top of the athlete-level store. So: athlete-level canonical store **+** a "your trips during this plan" review/edit/append panel in the create (and refresh) flow. The store is the source of truth; the panel is a windowed editor over it (changes write back to the athlete-level store, then feed the plan).
**Against:** an athlete might want a trip to affect only one plan. Mitigation: windows are date-bounded, so they naturally only touch plans whose span overlaps — good enough; a per-plan opt-out is YAGNI until asked.

### F2 — What identifies the destination?
- **(a) A `locale_profiles` row** — the athlete builds/picks a locale for the destination (terrain checkboxes + optional gym/equipment), exactly like a home locale; the window references it. The cascade reads it through the **existing** `cluster_terrain_by_locale` / `cluster_equipment_by_locale` machinery unchanged.
- **(b) A Mapbox-anchored inline place** (like `race_events`) — lighter to enter, but needs its own terrain/equipment capture + new cascade readers.
- **(c) Lightweight inline** (city + terrain checkboxes + `indoor_only`) — least reusable.

**RATIFIED (Andy 2026-06-14): destination = a `locale_profiles` row.** Flagged non-home (not `preferred`; outside the 42 km radius so it never leaks into the *home* cluster). Reuses the entire locale → terrain/equipment/override stack and the cascade's per-locale readers with zero new feasibility plumbing, and gives (b) craft↔location for free. **Andy's strategic rationale:** *"travel is how we will build our crowd-sourced locations database"* — every athlete's trip destination becomes a real, terrain/equipment-tagged locale, growing the shared `gym_profiles` / locale catalog (core differentiator #8, crowd-sourced data). This reframes away-windows from a niche feature into the **acquisition funnel for the crowd-sourced location DB** — a reason to weight the arc higher than its tier-4 origin.
**Against / residual:** a `locale_profiles` row historically means "a place I train regularly," and a one-off trip stretches that. Resolve with a discriminator (e.g. `kind`/`source='travel'`, or simply: any locale referenced by a window) rather than a parallel model — TBD in Slice-1 spec. Crowd-sourcing implies these away locales should be **shareable/dedupable by `mapbox_id`** (the `gym_profiles.mapbox_id UNIQUE` + `locale_profiles.mapbox_id` columns already exist) — note for the Slice-1 spec, not a blocker.

### F3 — How does the cascade become window-aware?
Feasibility becomes **time-varying**: a discipline can be `exact` at home but `indoor`/`strength` during an away window. Mechanism:
1. **Segment the plan timeline** into environments: the home cluster for non-window weeks, and each window's destination locale(s) for its weeks. (Granularity = **week**: each plan week maps to exactly one environment — the active window that week, else home. Overlap/precedence rule in §13.)
2. **Resolve the cascade once per distinct environment** (`_build_terrain_feasibility` already takes a locale set; call it per environment), producing `feasibility_by_environment: dict[env_key, dict[discipline_id, TerrainResolution]]`.
3. **Feed synthesis per week.** The per-phase prompt today gets one `terrain_feasibility` dict (`per_phase.py:840`). Change: pass a per-week mapping so each week in the `=== Session feasibility ===` block reflects that week's environment, with an explicit "Weeks X–Y: training away at <place>" callout.

**Recommend** this segment-then-resolve approach — it's the minimal change that keeps the pure cascade intact and reuses the per-(phase, week) grid the synthesizer already consumes.
**Against:** a phase straddling a window boundary now carries two feasibility pictures in one prompt — added prompt complexity and a Trigger-#1 wording change. Acceptable; the grid is already per-week so the seam is natural.

### F4 — Away craft default availability (the literal WS-H (b)+(c))
Issue #581: *"locale-aware for away locations while staying home-cluster-wide by default."*
- **Home cluster → all owned craft** (WS-G, unchanged).
- **Away locale → NONE by default**, availability added explicitly via:
  - **(b) craft↔locale** `athlete_craft_locale(user_id, craft_slug, locale)` — "I keep / can use this craft at this away locale" (a bike at a vacation home).
  - **(c) craft↔window** — the window carries a craft subset ("I'm bringing my packraft on this trip").
- Away `owned_crafts` for an environment = **(craft↔locale for that locale) ∪ (craft↔window for the active window)**, default empty.

**RATIFIED (Andy 2026-06-14): none unless declared.** You don't have your MTB on a work trip unless you say so; defaulting to "all craft everywhere" would re-introduce the over-availability that craft feasibility exists to prevent. Empty-away degrades gracefully through the existing cascade (terrain → indoor → strength → reallocate).
**Against:** more capture friction (the athlete must tick what they bring). Mitigation: a "bringing my usual craft?" shortcut can copy set B into a window — a UI nicety, not schema.

### F5 — Capture UI
A "Training away / trips" surface: build/pick the destination locale (reuse the locale builder), set the date window, tick craft brought. Profile section + optional onboarding step. **Sizable; spec now, build in the UI slice (§9).**

### F6 — Caching + refresh
Windows are athlete-level facts → a new `compute_travel_windows_hash` (windows overlapping the plan span + their craft subsets + destination locale digests) folds into `plan_create_key` **and** `plan_refresh_key`, mirroring `compute_terrain_feasibility_hash` (#556). Changing a trip invalidates exactly the affected synthesis. A refresh re-reads overlapping windows automatically (athlete-level, F1).

### F7 — Synthesis prompt (Trigger #1)
The `=== Session feasibility ===` block (#556) gains, for away weeks, a directive line: *"Weeks X–Y: training away at <place> — available terrain/equipment/craft: …; compose these weeks against THAT environment."* Exact wording **deferred to build** (Trigger #1 sign-off then). The cap/feasibility decisions stay deterministic in counts; the LLM only composes content.

### F-race — should the RACE trip auto-create an away window? (INVESTIGATED, Andy 2026-06-14)
Andy's prompt: *"are we surfacing the race location as a location? I don't think we are?"* — **Correct, we are not.** Finding:
- `race_events` models its location with **its own Mapbox-anchored fields** — `event_locale_name` / `event_locale_mapbox_id` / `event_locale_place_name` / `event_locale_lat` / `event_locale_lng` + `race_terrain JSONB` (`init_db.py:1392, 1414-1417`). Multi-day races carry a route graph: `race_route_locales` + `race_route_locale_equipment` (D-66).
- The `race_events.event_locale_id BIGINT FK → locale_profiles(id)` is **legacy/nullable** — the in-code comment (`init_db.py:1403-1408`) states the old "athlete's saved locale" semantic was **wrong** for race events and was replaced by the Mapbox-anchored fields.
- **So the race destination is a *parallel* model, NOT a `locale_profiles` row.** It carries terrain (`race_terrain`) but it is not in the athlete's locale/cluster world, and the training-week feasibility cascade never reads it. The race-week brief (D-66) is its only consumer.

**Implication for auto-window:** auto-creating an away window from the race event requires a **race-location → locale bridge** (convert the Mapbox-anchored event/route locale into a `locale_profiles` row the cascade can read). That bridge is *exactly* the F2 crowd-sourced-locations move applied to races — coherent and arguably desirable (the taper weeks before Pocket Gopher *should* compose against the race terrain), but it's a real new converter, not free, and it couples two models.
**Recommendation:** **do NOT bake race-auto-window into Slice 1.** Keep training-travel windows (athlete-declared) and the race location (Mapbox-anchored, race-week-brief-owned) separate for now; file the **race-location → locale bridge** as its own follow-up (it unlocks both auto-windowing *and* feeding race terrain into taper-week training feasibility). Revisit once the away-window foundation (Slice 1) proves the locale-reuse path. **→ Andy: confirm this deferral, or pull the race bridge forward if pre-race taper-at-destination is a near-term need (it is, for Pocket Gopher, July 17–19).**

---

## 5. Change surface (by slice)

- **DDL (owed Andy's hands — Neon egress blocked from the container):**
  - `athlete_travel_windows(id, user_id, start_date, end_date, destination_locale, notes, created_at)` — Slice 1.
  - `athlete_craft_locale(user_id, craft_slug, locale)` + a craft-subset carrier on the window (column or join) — Slice 2.
  - Locale discriminator for away destinations (F2) — Slice 1.
- **`layer4/orchestrator.py`** — segment plan weeks → environments; resolve `_build_terrain_feasibility` per environment; assemble per-environment `owned_crafts` (home=all, away=union). Slice 1 (terrain/equipment) + Slice 2 (craft).
- **`layer4/per_phase.py`** — per-week feasibility feed + the away callout in the feasibility block. Slice 1.
- **`layer4/hashing.py`** — `compute_travel_windows_hash` into both keys. Slice 1.
- **New `athlete_travel_repo.py`** + **`athlete_craft_locale_repo.py`** — reads/writes + Layer-1 eviction. Slices 1/2.
- **Capture UI** — `routes/` + `templates/` (reuse the locale builder). Slice 3.
- **Tests** — per slice.

Each slice stays under the 5-file substantive ceiling.

---

## 6. Slice plan / sequencing

- **Slice 1 — away-window foundation (terrain + equipment):** `athlete_travel_windows` + destination-as-locale (F2) + per-environment cascade resolution (F3) + per-week feasibility feed + cache hash (F6). **Away craft = none** (away weeks resolve terrain → indoor → strength only). Delivers the core away value (correct away terrain/equipment) end-to-end. DDL: `athlete_travel_windows` + locale discriminator.
- **Slice 2 — away craft (the literal WS-H (b)+(c)):** `athlete_craft_locale` + window craft-subset → away `owned_crafts` union (F4). DDL: `athlete_craft_locale` + craft carrier.
- **Slice 3 — capture UI (F5 + F1 panel):** trips surface on profile (+ onboarding), reusing the locale builder, **plus the plan-gen review/edit/append panel** (F1 — preserves the v1 `/coaching/review` UX over the athlete-level store). A minimal capture/review may fold into Slice 1 so the foundation is testable live.

This realizes the WS-H recommendation: away-craft is **one axis of the away-window feature**, sequenced after the foundation that gives it a consumer — never an unconsumed store.

---

## 7. Test scenarios (design-level)

1. No windows → byte-identical to today (home cluster, whole plan). *Regression guard.*
2. A window covering weeks 5–6 at a desert-city locale (treadmill gym, no water) → those weeks' D-009 Packrafting resolves `indoor`/`strength`, home weeks unchanged.
3. Window destination with trail terrain but craft NOT brought → MTB resolves terrain-feasible *foot* proxy or strength, not a ride (F4 none-default).
4. Same window with packraft ticked into the window (c) → D-009 resolves `exact` for those weeks only.
5. Craft↔locale (b): a bike kept at a recurring away locale → available whenever a window targets that locale, without re-ticking.
6. Window straddling a phase boundary → both phases' prompts carry the correct per-week split.
7. Cache: adding/moving a window invalidates only overlapping synthesis (hash test).
8. Overlapping windows / precedence (§13 rule) resolves deterministically.

---

## 8. Open items / Andy sign-off

**Ratified (2026-06-14):** F1 (athlete-level + plan-gen review/edit/append panel), F2 (destination = `locale_profiles`, crowd-sourcing funnel), F4 (away craft none-unless-declared). F3/F6/F7 follow with one sensible path each.

**Still owed before Slice 1 build:**
1. **F-race deferral** — confirm race-auto-window stays out of Slice 1 (the race→locale bridge is its own follow-up), OR pull it forward for Pocket Gopher taper.
2. **F2 residual** — away-locale discriminator shape (`source='travel'` vs implicit) + `mapbox_id` dedup for crowd-sourcing. Slice-1 spec detail.
3. **F1 panel placement** — minimal review/edit/append in Slice 1 (for live-testability) vs full panel in Slice 3.
4. **F7 prompt wording** — separate Trigger-#1 sign-off at build time (not now).

Slice 1 gets its own focused spec (the depth-standard layer/feature spec) once 1–3 are answered — this doc is the arc-level design, not the Slice-1 build spec.

---

## 9. Gut check

- **Value reframe (post-ratification):** F2's crowd-sourced-locations rationale (Andy) lifts this above its tier-4 origin — away-windows are the **acquisition funnel for the shared location DB** (differentiator #8), not just a niche convenience. That said, it's still mid-sized (3 slices, DDL); if the goal were purely *fastest value this session*, #542 (nutrition protein bug) is smaller. Andy chose the arc; this doc sizes it honestly.
- **Biggest risk: now retired by ratification.** F2 (locale-reuse) is locked, so the cascade-reader-doubling risk is gone. Residual: the away-locale **discriminator + `mapbox_id` dedup** shape (F2 residual) — a Slice-1 spec detail, not an arc risk.
- **race-trip overlap → resolved into F-race.** The race location is a *separate* Mapbox-anchored model, not a locale; auto-windowing needs a race→locale bridge (deferred, but flagged near-term-relevant for Pocket Gopher taper). **Andy to confirm the deferral.**
- **What might be missing:** (1) **Partial-week windows** (a trip starting mid-week) — the week-granularity model (F3) rounds to whole weeks; sub-week precision is likely YAGNI but should be a conscious call. (2) **Equipment-only trips** (hotel gym, no outdoor terrain) are already covered by destination-as-locale with empty terrain — no extra model. (3) The **review/edit/append panel** (F1) is real UI surface — sized into Slice 3, but a minimal version may need to ride in Slice 1 to make away-windows testable end-to-end.
- **Determinism:** consistent with the arc's "deterministic defensive routes" principle (Andy 2026-06-13) — windows decide *which environment* deterministically in code; the LLM only composes content for the environment it's handed.
