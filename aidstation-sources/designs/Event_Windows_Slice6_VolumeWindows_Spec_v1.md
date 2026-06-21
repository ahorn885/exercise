# Event Windows — Slice 6: reduced-volume / no-training (in-transit) windows — Build Spec v1

**Parent design:** `designs/Event_Windows_Design_v1.md` (F9 deferred the `reduced_volume` flag to its own issue). **This is the build spec for GitHub [#593](https://github.com/ahorn885/exercise/issues/593)** — the deferred fourth override family: a *volume* override (the athlete is **in transit** — flying, long drive — and trains **less or not at all**), as opposed to the three existing *feasibility* overrides (`indoor_only`, `locale_unavailable`, `away`).
**Status:** **DESIGN-FIRST — NOT BUILT.** Scoped per Andy 2026-06-21. Resolution model **settled 2026-06-21**: a single **deterministic capacity reduction** feeding the existing grid — explicitly *not* an LLM-reallocation / trim-to-fit cascade (Andy: that "introduces multiple new points of failure with the LLM looking for days or time slots it can't find"). Hits **Stop-and-ask Trigger #3** (new override type + cross-layer surface: schema + grid + cache hash). DDL owed Andy's hands / `layer0-apply`-adjacent. No build until §11 sign-off.
**Date:** 2026-06-21

---

## 1. Purpose + scope

Let the athlete declare date-bounded **volume windows** — travel days where they train less or not at all — and have plan-gen make that week **lighter**, deterministically, rather than placing a normal session on a day they can't use:
- **`reduced_volume`** — the day contributes a reduced share of capacity (an **athlete-set percentage per window**, §3); a lighter session can still land there.
- **`no_training`** — the day contributes zero capacity and is removed from the week's placement pool; nothing lands there.

The athlete's request (Andy, on #593): on a travel day they "train less or not at all"; the plan should scale the week down so they don't have to manually skip a session.

**In scope:** two new `override_type` values on the existing `athlete_event_windows` table; a **deterministic per-week capacity reduction** that lowers the windowed week's target hours and (for `no_training`) its enabled-day pool, feeding the **existing** grid so fewer/shorter sessions fall out of the math already in place; the synthesis directive naming the off-limit days; the cache hash (already folds new window fields generically); Rule #15 logging. Volume windows **union** with the feasibility overrides (§4) on overlapping dates.

**Out of scope:** new locations, craft, or terrain (Slices 2–4); changing *what* is feasible (the feasibility overrides — orthogonal, composed by union); **LLM-driven reallocation / repacking** (deliberately rejected, §2); volume conservation / hand-picking which session survives (the reduction is proportional, §4).

**Success criteria:**
- (a) No volume windows → byte-identical plans (regression).
- (b) A 1-day `no_training` window → that day is empty and the week's deterministic session count drops to fit the remaining days; the LLM places a smaller set with **no off-limit day to hunt for** (count ≤ available days by construction).
- (c) A `reduced_volume` window → the week's capacity drops by that day's reduced share; a lighter session can occupy the day; fewer/shorter sessions overall.
- (d) Adding/moving a volume window invalidates only overlapping synthesis.

---

## 2. Boundaries

- **The reduction is deterministic; the LLM never repacks.** This is the load-bearing decision (Andy 2026-06-21). The grid already converts weekly target hours → session count (`session_grid._allocate_discipline`, `session_grid.py:383`). A volume window simply feeds it **less weekly capacity** for the windowed week, so fewer/shorter sessions fall out of the existing math. The LLM then places a normally-sized (smaller) set. **Because the count is reduced to match available capacity, session count ≤ available days by construction** — the model is never asked to find a slot that doesn't exist. This is precisely what avoids the "LLM hunting for days it can't find" failure mode; there is **no** reallocate / reformat / trim-to-fit cascade.
- **No volume conservation.** A skipped day makes the week lighter; it does **not** shuffle the freed session onto another day to preserve weekly volume. That's the intended, honest outcome — "train less on travel days," not "cram the same week into fewer days" — and it's the safe one (no over-packing).
- **No bespoke session-priority list.** The grid's existing phase logic already protects structure (e.g. `_intensity_mix` floors a hard session in Build/Peak, `session_grid.py:430`). The reduction scales the week proportionally; key structure survives via the rules already in place, not a new priority order. (Manual escape hatch if a specific key session must be protected: don't mark that day, or mark it `reduced_volume` rather than `no_training`.)
- **A volume window does not change *feasibility*.** It changes *how much*, not *what kind*. On a day that is both `no_training` and (say) `away`, the volume override removes the day; the away feasibility for that day is simply unused. The two override families compose by **union** (§4), reusing the Slice-1 overlapping-windows union path.

---

## 3. Data model (DDL — owed Andy's hands / `layer0-apply`-adjacent)

Extend `athlete_event_windows` (idempotent `_PG_MIGRATIONS` migration), no new table:

| Column | Type | Notes |
|---|---|---|
| `override_type` | TEXT | gains `reduced_volume` \| `no_training` (now: `indoor_only` \| `locale_unavailable` \| `away` \| `reduced_volume` \| `no_training`) |
| `volume_pct` | NUMERIC NULL | the retained fraction of that day's capacity for `reduced_volume`, **athlete-set per window** (0 < pct < 1). NULL for every other type. `no_training` is 0% + removed from the day pool (stored as the discrete type, not pct=0, so it reads cleanly). |

- **Per-window slider** (decision 2026-06-21 — Andy chose the dial over a fixed constant). The athlete sets `volume_pct` when they declare a `reduced_volume` window (a percent/fraction control on the capture form, §5). A sensible default (e.g. 0.5) pre-fills the control but the athlete can override per window — a half-day travel day vs a near-full day differ.
- `OVERRIDE_TYPES` (`athlete_event_windows_repo.py:39`) gains the two values; `add_event_window` validation (`athlete_event_windows_repo.py:150`) requires `volume_pct ∈ (0,1)` iff `reduced_volume` (NULL otherwise) and **clears all locale fields** (`unavailable_locale`, `away_locale`, `brought_craft`) for both new types (they carry no location — mirrors the `indoor_only` clear at `athlete_event_windows_repo.py:186`).
- No CHECK constraint (project no-CHECK convention); enforced in app code.

---

## 4. Resolution model — deterministic capacity reduction into the existing grid

This is the **first override that touches counts** (Slices 1–2 deliberately left counts on the home environment — Slice 1 §4 ¶3). The feasibility cascade is untouched; the new element is a **per-week capacity reduction** computed before the grid runs.

1. **Load + union the windows for the plan span** (existing `_build_event_window_overlay`, `orchestrator.py:770`). Volume windows are collected alongside the feasibility windows; on overlapping dates the union carries *both* a feasibility reduction (from indoor/locale/away) *and* a capacity reduction (from reduced/no-training). Reuses the Slice-1 overlapping-windows union edge case.
2. **Per affected week, compute the capacity factor.** Each day contributes `1.0` normally, the window's **`volume_pct`** if `reduced_volume`, `0.0` if `no_training`. The week's **capacity factor** = (sum of day contributions) ÷ (normal enabled-day count). Example: a 6-enabled-day week with one `no_training` day → factor `5/6 ≈ 0.83`; with one `reduced_volume` day at `volume_pct=0.5` → factor `5.5/6 ≈ 0.92`; the athlete could instead set that day to `0.25` → `5.25/6 ≈ 0.875`.
3. **Scale the week's target hours, then run the existing grid.** Multiply the windowed week's per-discipline target hours by the capacity factor and call `_allocate_discipline` (`session_grid.py:383`) **unchanged** — fewer hours in → fewer/shorter sessions out, by the math already in place. No new "trim" step; no priority list. `no_training` days are additionally removed from the week's enabled-day pool so nothing is placed on them.
4. **Synthesis places the smaller set.** `per_phase._format_event_window_overlay` (`per_phase.py:1612`) renders a volume directive for the windowed dates: *"Days X–Y: in-transit — no training (day unavailable) | reduced volume (light session only). The week has already been scaled lighter; place the listed sessions on the available days."* The LLM places (its existing job) across the available days. **Because the count was scaled to the reduced capacity, the available days always suffice** — the model never hunts for a missing slot. A session that lands on a `reduced_volume` day composes lighter through the existing intensity machinery; no bespoke logic.

**Why this is robust.** The only behavioral change the LLM sees is "this week has fewer sessions and (for no-training) one fewer day" — both of which it already handles every week (weeks already differ in count and enabled days). The reduction is pure arithmetic on inputs the grid already consumes. There is no new constraint that can be unsatisfiable, so there is no new failure surface (Andy 2026-06-21).

**Accepted limitation (mirrors Slice 1 §4 ¶5).** A scaled week falls **below** the validator's phase volume band (`validator.phase_week_volume_bands_hours`). For genuine travel weeks that's correct (the athlete *is* training less), and the band rule is advisory. The clean fix — feed the validator the same capacity factor for windowed weeks so it bands against reduced capacity — is deferred to when it bites; flagged in §11.

---

## 5. Change surface (≤5 substantive files)

1. **`athlete_event_windows_repo.py`** — add the two `override_type` values + `volume_pct` validation/clearing + load it onto the window record.
2. **`init_db.py`** — idempotent migration adding the `volume_pct` column + registering the two new `override_type` values if any enum/constraint mirrors them.
3. **`layer4/session_grid.py`** — the per-week capacity factor (reads each window's `volume_pct` for `reduced_volume`, 0 for `no_training`); scale target hours before `_allocate_discipline`; drop `no_training` days from the enabled-day pool. **The one genuinely new code** (small — a multiply + a day-pool filter; no new arithmetic engine).
4. **`layer4/orchestrator.py`** — collect volume windows in `_build_event_window_overlay`; pass the per-week capacity factor + off-limit days into the grid call. Rule #15 log of the factor + resulting count delta.
5. **`layer4/per_phase.py`** — render the volume directive in `_format_event_window_overlay` (Trigger-#1-adjacent wording; the overlay block already exists from Slice 1, so this is an added clause, not a new prompt — see §11).
- **Capture UI** — add the `volume_pct` percent control to the event-window add/edit form, shown only when `override_type=reduced_volume` (thin; reuses the existing window form. May ride file 1's route or a 6th thin template — flag at build if it pushes the ceiling).
- **Caching:** `compute_event_windows_hash` (`hashing.py:186`) digests all window fields generically; add `volume_pct` to the flattened dict (one line) so a slider change invalidates the overlapping synthesis; the two new `override_type` values ride the existing digest and fold into both plan keys automatically.
- **Tests** (not counted): extend `tests/test_layer4_event_windows.py` + `tests/test_athlete_event_windows_repo.py` with the success-criterion scenarios (incl. distinct `volume_pct` values).

---

## 6. Caching

`compute_event_windows_hash` already keys on `override_type + dates (+ all window fields)`; the two new types plus `volume_pct` ride the digest → a volume-window edit (including a slider change) invalidates exactly the overlapping synthesis (success criterion (d)); no-windows stays byte-identical (success criterion (a)).

---

## 7. Rule #15 logging

Per windowed week, print inputs + decision:
`volume_window_scale: <phase>:w<W> dates=<range> types=[no_training:<dates>,reduced_volume:<dates>] factor=<0.83> enabled_days=<6->5> count=<m-> n> hours=<H-> H'>` — naming the capacity factor, the day-pool change, and the **pre/post session count + hours**, so a surprising lighter week is diagnosable from logs alone (Rule #15). The decision is pure arithmetic, so the log fully explains it.

---

## 8. Edge cases
- **Volume window over a day in a light week** → the week scales down by that day's share; the week is ~1 session lighter (no conservation — by design, §2).
- **`no_training` covering a whole week** → capacity factor 0 → zero sessions; the week becomes a full rest week (logged). Validator under-volume is expected (§4 limitation).
- **`reduced_volume` + `indoor_only` same day** → union: the day is half-capacity *and* indoor-only; whatever light session lands there composes at the indoor tier. No new logic.
- **`reduced_volume` + `away` same day** → union: the day is half-capacity; the away environment is mostly unused that day. (Common real case: the *travel* day is `no_training`/`reduced`, the *arrival* days are `away`.)
- **Window outside the plan span** → ignored (hash unaffected) — existing Slice-1 behavior.
- **All enabled days `reduced_volume`** → factor 0.5 → roughly half the week's sessions, all able to be lighter; no day removed from the pool.

---

## 9. Test scenarios
1. No volume windows → identical grid + cache key. *Regression.*
2. `no_training` 1 day in a 6-day week → factor 5/6; week's count drops accordingly; that day not in the placement pool; resulting count ≤ available days. *(criterion b)*
3. `reduced_volume` 1 day → factor 5.5/6; slightly fewer/shorter sessions; day still placeable for a light session. *(criterion c)*
4. `no_training` whole week → zero sessions; full rest week; validator under-volume tolerated; logged. *(§8)*
5. `reduced_volume` unioned with `indoor_only` same dates → both reductions apply; light session composes indoor. *(§8)*
6. Cache: add/move/delete a volume window → only overlapping weeks' synthesis recomputes. *(criterion d)*
7. Rule #15 `volume_window_scale` line present + correct (factor, day-pool change, count/hours delta).

---

## 10. Why this is small
The cascade, the overlay rendering, the union path, the hash, the grid's hours→count math, and the LLM placement contract are **all reused**. The only genuinely new code is: two enum values + a `volume_pct` column (§3), a thin capture control, and a **per-week capacity multiply + a `no_training` day-pool filter** in `session_grid.py` (§4). No reallocation engine, no trim-to-fit, no priority list, no new constraint the LLM can fail — that's the whole point of the deterministic-reduction model.

---

## 11. Open items / sign-off
- **Resolution model — SETTLED** (Andy 2026-06-21): deterministic capacity reduction into the existing grid; no LLM reallocation / trim-to-fit. **Spec'd.**
- **`reduced_volume` factor — SETTLED** (Andy 2026-06-21): a **per-window slider** (`volume_pct`, 0–1), athlete-set, default-filled (~0.5). Adds the `volume_pct` column (§3) + the capture control (§5). **Spec'd.**
- **Trigger #1 wording — OWED at build.** The volume directive added to the existing event-window overlay block (`per_phase._format_event_window_overlay`). It extends a shipped prompt rather than authoring a new one, but the clause wording still needs sign-off at build (matches Slice 1's Trigger-#1 treatment).
- **Validator band under windowed weeks — accepted limitation now; clean fix deferred** (feed the validator the same capacity factor for covered weeks). (§4)
- **DDL apply** — register the two `override_type` values via `init_db._PG_MIGRATIONS` (owed Andy's hands / `layer0-apply`-adjacent).

## 12. Gut check
- **Best argument against building it:** Andy deferred this once for a reason — a travel day is trivially handled by skipping a session manually. The feature earns its keep only if travel is frequent enough that manual skipping is annoying. The deterministic-reduction model at least makes it *cheap and safe* to build, so the bar to ship is low.
- **Biggest risk — now small.** The earlier draft's risk (LLM repacking, wrong-session drops) is **designed out**: the reduction is pure arithmetic and the LLM sees only a normal smaller week. The residual risk is purely cosmetic — a travel week might scale down the one long session you cared about. Mitigation is manual (don't mark that day, or use `reduced_volume`); not worth priority logic.
- **What's genuinely clean:** modeling volume as a separate `override_type` that **unions** with the feasibility overrides means travel-day + away/indoor compose for free; and feeding a capacity factor into the *existing* grid means the "new" behavior is arithmetic on inputs the grid already takes — minimal surface, no new failure mode.
- **What might be missing:** the **refresh** path — if the athlete logs a travel day *after* the plan is built, the volume-window hash change should trigger a T1/T2 refresh of the affected week (falls out of the existing window→hash→refresh loop, F6, once volume windows feed the hash — worth a refresh-path test).
