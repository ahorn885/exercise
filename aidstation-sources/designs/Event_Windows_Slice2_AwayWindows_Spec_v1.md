# Event Windows — Slice 2: away windows + destination locale — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (forks ratified 2026-06-14; Slice 2 = §6 bullet 2). **Predecessor:** `designs/Event_Windows_Slice1_HomeWindows_Spec_v1.md` (BUILT + LIVE, PR #596) + the refresh-overlay follow-up (PR #599). **This is the Slice-2 build spec** — the third `override_type`, `away`: a date-bounded period where the athlete trains from a *different* location whose environment **replaces** the home cluster.
**Status:** **DESIGN-FIRST — awaiting sign-off.** Trips **Trigger #1** (new away-overlay directive wording) + **Trigger #3** (new DDL: one `away_locale` column). No code until §10 is signed off. **Revised 2026-06-14 (Andy):** away env = the destination's own radius cluster (re-anchored `cluster_locale_ids`, *same logic as home*) — the `locale_profiles` discriminator is dropped; confirmed there is one unified cascade, not two (§2).
**Date:** 2026-06-14

---

## 1. Purpose + scope

Let the athlete declare a date-bounded **`away` window** — *"I'm at a different location these dates"* — and have plan-gen resolve those days against **that location's** terrain/equipment instead of the home cluster. Where Slice 1's two override types **subtract** from the home cluster, `away` **replaces** it (design §3).

- **`away(dest)`** — for the window's dates, the environment is the destination `locale_profiles` row's terrain + equipment. **Away craft defaults to none** (F4) — bike/paddle disciplines degrade through the cascade (terrain → indoor → strength → reallocate) unless the destination locale itself carries the terrain/equipment. (Declared brought-craft is **Slice 4**, not here.)

**In scope:**
1. A third `override_type='away'` on `athlete_event_windows` + an `away_locale` reference to a saved `locale_profiles` row — **the cluster *anchor*** for the window (§3).
2. **Re-anchored clustering (Andy 2026-06-14):** the away environment is the **same `cluster_locale_ids` radius sweep, anchored at the destination** — the away_locale + every saved locale within `_CLUSTER_RADIUS_KM` (26.2 mi) of it — not just the single destination row. Identical logic to how home clusters around the `preferred` locale (§4).
3. A **replacement** environment branch in the date-segment resolver: build `(locale_order=away_cluster, terrain, equipment, owned_crafts=[])` from the away anchor's cluster and run the **existing** cascade (§4). No new resolution logic — same EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE walk (with the craft tiers, §4), different inputs.
4. The away-aware overlay render + label (Trigger #1, §7) and the cache hash folding in `away_locale` (§6).
5. **Minimal away-window capture:** pick an **existing saved** locale as the destination. (Inline-create-new-destination — F1/F2's "the location may not exist yet" — is called out in §5 as a likely file-ceiling split to the UX slice; see §10 decision.)

**Out of scope (later slices):** declared away **craft** (Slice 4, the literal WS-H (b)+(c)); category **equipment baselines** + the assumed→logged **arrival-regen** loop (Slice 3, Trigger #2); full capture/inline-create **UX** (Slice 5); `reduced_volume` in-transit days (#593); race-location inference (#592).

**Success criteria:** (a) no `away` windows → byte-identical to Slice-1 behavior (regression); (b) an `away` window on a destination with trail terrain → trail-run resolves `exact` for those dates against the **away cluster** (anchor + radius), not the home cluster; (c) an `away` window on a destination with **no** bike terrain and the athlete brings no craft → the MTB days degrade (indoor/strength per the cascade), and the **home** days are unaffected; (d) the away cluster forms by the **same radius sweep** as home, re-anchored at the destination (a far destination → its own clean cluster with no home locales in range); (e) adding/moving an `away` window invalidates only overlapping synthesis.

---

## 2. Boundaries

- **`away` replaces, it does not subtract.** The away segment's environment is built fresh from the destination's **own radius cluster** (anchor + 26.2 mi, §4), not the home maps with something removed. The two Slice-1 subtractive types are untouched.
- **One cascade, not two (answers Andy's drift question).** There is a single unified feasibility cascade (WS-I Slice B, #588). Craft disciplines (bike/paddle) walk `resolve_craft_terrain_feasibility` (craft tiers 1–4 → INDOOR → STRENGTH → REALLOCATE); non-craft (foot/swim/climb) walk `resolve_terrain_feasibility` (EXACT → PROXY → **same** INDOOR → STRENGTH → REALLOCATE tail) — the non-craft path is just the craft cascade minus the four tiers that can never fire. `_resolve_included_feasibility` dispatches every discipline through the craft function, which returns `None` for non-craft → caller falls to the terrain-only path. **Away reuses this exact cascade** — `owned_crafts=[]` simply means the craft tiers find nothing and the walk degrades through INDOOR→STRENGTH→REALLOCATE (the same craftless degradation that already runs at home post-#588). No away-specific rule. *(One honest DRY smell: the INDOOR→STRENGTH→REALLOCATE tail is physically duplicated across the two functions — behavior is identical; a `simplify` candidate, not in this slice's scope.)*
- **Away craft = none (F4).** The away environment's `owned_crafts` is `[]` in Slice 2 — the athlete's home-cluster crafts do **not** travel automatically. Declared brought-craft is Slice 4. This makes `owned_crafts` **environment-dependent** for the first time (home = all owned; away = none), a small but real change to the resolver signature (§4).
- **Counts: unchanged in Slice 2 (recommended) — the main open decision (§10).** Like Slice 1, the grid + E2 saturation cap resolve against the **home** environment; the away window only re-scopes the *per-date* feasibility synthesis composes against. For short away windows (a few days) this is correct and conserves volume. For a **whole-week / multi-week** away window it carries the documented Slice-1 limitation (§4): E2 won't pre-cap a substitution the away env forces. Feeding the grid/E2 the segment tiers for fully-covered weeks is the heavier alternative — **deferred unless Andy wants it in Slice 2** (§10). This is the F3 risk the arc design flagged.
- The LLM's job is unchanged in kind: it **places** sessions on days and composes each against its date's deterministic cascade tier; it never decides feasibility or counts.

---

## 3. Data model (DDL — owed Andy's hands, Neon egress blocked)

**One** idempotent `_PG_MIGRATIONS` ALTER (no new table, no discriminator):

**`athlete_event_windows` — add the away anchor column + the third type:**

| Column | Type | Notes |
|---|---|---|
| `away_locale` | TEXT NULL | the destination `locale_profiles.locale` slug — the **cluster anchor** — when `override_type='away'`; NULL otherwise |

`override_type` gains a third value `away` (no DB CHECK — the closed set lives in `OVERRIDE_TYPES` in the repo, per the project's no-CHECK convention). App-code constraints (in `athlete_event_windows_repo`): `away_locale` **required + must resolve** to one of the athlete's `locale_profiles` rows iff `override_type='away'`, and is cleared otherwise (mirrors the `unavailable_locale` handling). `end_date >= start_date` unchanged.

**No `locale_profiles` discriminator (revised, Andy 2026-06-14).** An earlier draft added a `kind` (`home`/`away`) column to keep away destinations out of the home-cluster radius sweep. Andy's re-anchoring guidance dissolves the need: the away environment is the destination's **own** radius cluster (§4), and a locale is just a geographic point. A far destination (Belfast) self-excludes from the home cluster by distance; a destination saved *within* home radius is genuinely reachable from home, so its appearing in the home cluster on non-window days is geographically honest, not pollution. **Net: drop the discriminator** → the DDL is one column, and `locale_profiles` is untouched. (Accepted tradeoff: a within-radius destination contributes to the home default env on non-window days — §8.)

---

## 4. Resolution model — replacement env, same cascade (extends Slice-1 §4)

Slice 1 established: *a window is just different `(terrain, equipment)` inputs to the existing cascade, resolved per date-segment* — `segment_window_boundaries` cuts the span, `_resolve_included_feasibility` runs the unchanged EXACT→PROXY→INDOOR→STRENGTH→REALLOCATE walk per environment. Slice 2 adds **one new way to build the per-segment environment** and **one new degree of freedom** (away crafts). No new resolution logic.

**The new env-build branch.** Slice 1's `_reduced_env(fi, overrides)` returns `(locale_order, terrain, equip)` by *subtracting* from the home maps. Slice 2 generalizes the per-segment env build so an `away` override yields a **replacement**:

1. **`away` present in a segment's active overrides** → build the destination env from the **away anchor's radius cluster** (Andy 2026-06-14 — *same logic as home*):
   - `away_cluster = locations.cluster_locale_ids(db, user_id, anchor_locale=away_locale)` — the away_locale + every saved locale within `_CLUSTER_RADIUS_KM` (26.2 mi) of it, anchor first. Requires **generalizing `cluster_locale_ids` to take an `anchor_locale` param** (default `None` → today's `preferred` home anchor, byte-identical; §5).
   - `locale_order = away_cluster`
   - `terrain_by_locale = locations.cluster_terrain_by_locale(db, user_id, away_cluster)`
   - `equip_by_locale  = locations.cluster_equipment_by_locale(db, user_id, away_cluster)`
   - `owned_crafts = []`  *(F4 — Slice 4 supplies the declared brought-craft set; the cascade still runs its craft tiers, they just find nothing — §2)*
   - **Precedence:** `away` is a *replacement*, so when it co-occurs with a subtractive override on the same segment, `away` wins and the subtractive override is **ignored** (logged). You can't be "home indoor-only" and "away" the same day. (Multiple `away` windows can't legitimately overlap the same date; if they do, pick the first by `(start_date, id)` and log — edge, §8.)
2. **No `away`** → unchanged Slice-1 subtractive path (`_reduced_env`).

**`owned_crafts` becomes per-environment.** Today `_resolve_included_feasibility(fi, *, locale_order, terrain_by_locale, equip_by_locale)` reads crafts from `fi.owned_crafts`. Slice 2 adds an optional `owned_crafts: list[str] | None = None` kwarg (default `None` → `fi.owned_crafts`, byte-identical for home + Slice-1 segments; `away` passes `[]`). The cascade already takes `owned_crafts` as a parameter — this only threads the per-segment value through. **Regression-safe:** every existing caller omits the kwarg and gets `fi.owned_crafts` exactly as today.

3. **Run the existing cascade once per environment** (home, subtractive segments, away segments) → `feasibility_by_segment[date_range] → dict[discipline → tier]`. Emit only disciplines whose away-env routing **differs** from home (the Slice-1 `changed` filter, unchanged).
4. **Counts stay on home** (§2; the recommended Slice-2 scope). The grid + E2 are unchanged.
5. **Synthesis composes per date** — `per_phase._format_event_window_overlay` renders the away segment date-scoped (the away env + its tiers), now with away-aware wording (§7). The LLM places + composes each session against its date's tier, exactly as Slice 1.

---

## 5. Change surface (≤5 substantive files — flag the ceiling, see §10)

1. **`athlete_event_windows_repo.py`** — add `'away'` to `OVERRIDE_TYPES`; `away_locale` field on `EventWindow`; load/add validation (required+resolvable iff `away`, cleared otherwise — mirror of `unavailable_locale`). Eviction unchanged (already scoped to `plan_create`/`plan_refresh`).
2. **`layer4/session_feasibility.py`** — `EventWindowOverride.override_type` `Literal` gains `'away'`; add an `away_locale: str | None = None` field. `segment_window_boundaries` is **unchanged** (it's override-type-agnostic — it already cuts on any window's boundaries and unions actives; precedence is applied downstream in the env-build, §4).
3. **`layer4/orchestrator.py`** — generalize the per-segment env build (the `away` replacement branch + precedence + the `owned_crafts=[]` pass); thread the optional `owned_crafts` kwarg through `_resolve_included_feasibility`; Rule #15 away log (§7). `_build_event_window_overlay` maps each window's `away_locale` into the `EventWindowOverride`.
4. **`locations.py`** — **generalize `cluster_locale_ids(db, user_id, anchor_locale=None)`**: `None` → resolve the anchor from the `preferred` home row (today's behavior, byte-identical for every existing caller); a supplied `anchor_locale` → anchor the radius sweep at that locale's lat/lng. The away path passes `anchor_locale=away_locale`. The existing Rule #15 cluster log already prints the resolved cluster + anchor.
5. **`layer4/per_phase.py`** — `_event_window_label` away branch + the overlay block intro made away-aware ("reduced **or replaced**", §7). Trigger-#1 wording.

**Capture UI** — minimal: an `away` row type on the existing `/profile/event-windows` form with a **destination dropdown of the athlete's saved locales** (reuse the existing locale list; `kind='away'` rows + home-cluster rows both selectable as a destination). Route + template are thin edits to the Slice-1 capture.

**DDL migration** rides in `init_db.py` (bookkeeping-adjacent).

**File-count flag:** items 1–5 are five substantive files **before** any inline-create UX. **Inline-create-a-new-destination** (F1/F2 — "the event's location may not exist yet", which would reuse `routes/locales.py new_locale` + `mapbox_id` dedup) would push past the ceiling. **Recommendation (§10):** Slice 2 ships the resolution + schema + *pick-an-existing-saved-locale* capture; **inline-create folds into the UX slice (Slice 5)** or a `2b`. This keeps the risky new machinery (re-anchored away cluster, replacement env, per-env crafts) behind ≤5 files and defers pure UX. *(Dropping the discriminator also removes its `init_db.py`/`locale_profiles` touch, leaving more ceiling headroom.)*

---

## 6. Caching

`compute_event_windows_hash` (Slice 1: digest of overlapping windows' `type + dates + unavailable_locale`) **folds in `away_locale`** so an `away` window — or a change of destination — re-keys `plan_create` + `plan_refresh` (the refresh-overlay path is already wired, PR #599). No-`away`-windows → identical digest → byte-identical key (success criterion (a)).

**Destination *content* edits.** If the athlete edits a destination-cluster locale's equipment/terrain, that should re-plan the overlapping window. Editing a `locale_profiles` row already evicts the plan caches (the Slice-1 + #540 locale-edit eviction path), and since away locales are ordinary `locale_profiles` rows (no discriminator), they hit the same path. The away env's equipment is read live at resolution (`cluster_equipment_by_locale` reads the row at plan-gen). The **assumed→logged arrival-regen loop** (F6/F8) is **Slice 3** — Slice 2 reads whatever the destination cluster currently holds.

---

## 7. Rule #15 logging + Trigger-#1 wording

**Logging (inherited + extended).** The shared `_build_event_window_overlay` already emits one decision line per segment. The away branch extends it to name the replacement env + the empty craft set, so a surprising away-day plan is diagnosable from logs alone:

```
event_window_overlay: user_id=… dates=…..… override=away:<locale> \
  env_terrain={…} env_equip={…} owned_crafts=[] tiers={D-008:strength, D-001:exact, …}
```

(`owned_crafts=[]` is printed explicitly — the #1 reason an away bike/paddle day lands on strength is "no craft travelled", and Rule #15's pv=69 lesson is to log the *input that drove the decision*, not just the outcome.)

**Trigger-#1 wording (DRAFT — needs Andy's sign-off).** Two touch-points:

- **`_event_window_label` away branch** (replaces the defensive `else` that currently echoes the raw type):
  > `away at "<destination label>" (training environment: that location's terrain/equipment; no brought craft)`
- **Overlay block intro** — Slice 1 says *"the training environment is **reduced**."* Make it away-aware:
  > "Part of this block falls inside a declared event window where the training environment **differs** — either **reduced** (home, indoor-only or a locale closed) **or replaced** (training away at another location). On the dates below, routing differs from the default feasibility block above. Compose any session dated within a window against THAT window's routing; sessions outside the windows use the default. Counts are unchanged — a session that lands on a window day is composed at that day's environment, never dropped."

Tone follows the project voice (direct, no hype). Final wording is Andy's call (Trigger #1).

---

## 8. Edge cases

- **`away_locale` deleted/missing at plan-gen** → the destination resolves to empty terrain+equipment → disciplines degrade through the cascade (indoor/strength). Log it (`away:<locale> row_found=False`); don't crash. (The repo validates resolvability at *write* time, but a later locale delete can orphan it.)
- **Destination with empty terrain *and* equipment** (a bare new locale, no gym linked) → everything degrades to strength/reallocate — the honest answer for "away with nothing logged." Slice 3's baselines soften this; Slice 2 reports it via the Rule #15 line.
- **`away` overlaps a subtractive window on the same dates** → `away` wins (replacement); the subtractive override is dropped + logged (§4).
- **Two `away` windows overlap the same date** → first by `(start_date, id)`; log the conflict. (Shouldn't happen — you're in one place — but the segmenter must be deterministic.)
- **Away destination saved within `_CLUSTER_RADIUS_KM` of home** → it *also* appears in the **home** cluster on non-window days (no discriminator). Accepted (§3): it's genuinely within home's training radius, so this is honest, not pollution. On its window days the env re-anchors to it (its own cluster).
- **No `away` windows at all** → `compute_event_windows_hash` digest is identical to Slice 1 → byte-identical plan (regression).
- **`away` window fully covers a plan week** → every day is the away env; the discipline's whole-week tier is the away cascade result. (Counts still computed on home — the documented §2 limitation; whole-week is exactly where Andy's count-shift concern lives, §10.)

---

## 9. Test scenarios

1. No `away` windows → identical grid + feasibility + cache key to Slice 1. *Regression.*
2. `away` on a destination with trail terrain → trail-run `exact` for the window dates (resolved against the **away cluster**, not home); home days unchanged.
3. `away` on a destination with **no** bike terrain, athlete brings no craft → MTB days degrade (indoor/strength per the *same* cascade), `owned_crafts=[]` in the Rule #15 line; home-day MTB still `exact`.
4. `cluster_locale_ids(anchor_locale=away)` → away anchor first + only locales within radius of the away anchor (a second saved locale near the destination joins the away cluster; a far home gym does not). `anchor_locale=None` → byte-identical to today's preferred-home cluster (regression).
5. `away` + `indoor_only` declared on the same dates → `away` env resolves; the subtractive override is dropped + logged (precedence).
6. `away_locale` deleted between save and plan-gen → no crash; degrades; `row_found=False` logged.
7. `compute_event_windows_hash` changes when `away_locale` is added/changed; byte-identical when no away windows.
8. Cache: add/move/delete an `away` window → only overlapping weeks' synthesis recomputes (create **and** refresh — #599 path).
9. `EventWindowOverride` away wiring: `segment_window_boundaries` cuts an away window's boundaries + carries the `away_locale` through to the env build.

---

## 10. Open items / sign-off

| # | Item | Trigger | Recommendation / status |
|---|---|---|---|
| 1 | **Counts on home vs feed-the-grid the away segment tiers** for whole-week away windows (the F3 risk). | architecture | **Keep counts on home in Slice 2** (smallest surface; documented limitation; matches Slice 1). Feed-the-grid is a heavier seam — defer unless you want it now. **This is the load-bearing call — still open.** |
| 2 | **Away cluster = anchor + radius** — the away env is the destination's own `cluster_locale_ids` sweep, generalized to take an `anchor_locale`. | architecture | **RESOLVED (Andy 2026-06-14): same logic as home, re-anchored.** Discriminator dropped. |
| 3 | **`away_locale` column** on `athlete_event_windows` + `override_type='away'` (the cluster anchor). | #3 schema | As §3 — one ALTER. Mirror of `unavailable_locale`. |
| 4 | **Trigger-#1 away wording** — the `_event_window_label` away branch + the away-aware block intro (§7 draft). | #1 prompt | Sign off §7 verbatim or edit. **Still open.** |
| 5 | **File ceiling / inline-create split** — ship resolution + schema + *pick-existing* capture in Slice 2; **defer inline-create-a-new-destination to the UX slice**. | — | **Defer inline-create** — keeps Slice 2 ≤5 substantive files behind the risky machinery; inline-create is pure UX over the same schema. **Still open.** |
| 6 | **Destination-edit eviction** confirm — an away locale edit hits the existing plan-cache eviction. | — | Verify at build (same `locale_profiles` table → same path); the assumed→logged arrival loop is Slice 3. |

**DDL owed Andy's hands** (Neon egress blocked): the single `away_locale` ALTER in §3, applied on Neon, idempotent `_PG_MIGRATIONS` shape.

---

## 11. Gut check

- **The new surface is genuinely small** — generalize `cluster_locale_ids` to take an anchor (one param, default-None = byte-identical), one new env-build branch (replacement instead of subtraction), one new env-dependent input (`owned_crafts=[]`), one `away_locale` column. The substitution intelligence is **entirely reused** from the existing single cascade (§2), exactly as Slice 1 reused it. The risky part isn't the cascade; it's the counts question (§10 #1).
- **Biggest risk: the counts decision (§10 #1).** For short away trips, counts-on-home is correct and cheap. For a 2-week training camp it under-counts the destination's feasibility into the weekly grid — the F3 seam Andy flagged. I recommend shipping counts-on-home (consistent with Slice 1, smallest vertical) and only building the feed-the-grid seam if a real whole-week-away plan shows the limitation biting. **If you'd rather solve it now, that changes the slice's size and file count — flag before I build.**
- **F4 (away craft = none) is the right default** — it degrades honestly through the *same* cascade (no craft travelled → the craft tiers find nothing → strength/indoor) and keeps Slice 2 free of the craft-carrier DDL (that's Slice 4). The Rule #15 `owned_crafts=[]` line makes the "why strength?" answer obvious, per the pv=69 lesson.
- **Re-anchoring is cleaner than the discriminator I first proposed** — treating the away env as the destination's own radius cluster (Andy's call) reuses `cluster_locale_ids` wholesale, removes a column + a `locale_profiles` touch, and is more correct (a destination with a nearby gym/park the athlete also saved picks both up). The only cost — a within-radius destination contributing to home on non-window days — is geographically honest.
- **Inline-create deferral (§10 #5) is a real scope cut** — F1/F2 want "the location may not exist yet → create it inline." Deferring it to the UX slice means Slice 2's away capture only picks an **existing** saved locale. That's a smaller athlete-facing story but keeps the file ceiling honest; if you want inline-create *in* Slice 2, we should split the resolution (2a) from the capture (2b) rather than breach the ceiling.
- **Best argument against doing Slice 2 next:** Slice 3 (category baselines) is what makes away *useful cold* — an away window on a never-seen hotel gym resolves to near-strength without a baseline. Slice 2 without Slice 3 is "away works but only if you've already logged the destination's equipment." That's still correct and shippable (and it's the right dependency order — the env must exist before a baseline can seed it), but worth naming: the athlete-visible payoff of away lands fully with Slice 3.
